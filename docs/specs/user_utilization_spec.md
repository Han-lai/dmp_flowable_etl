# 人員使用率 (User Utilization) - End-to-End 技術規格書

**版本:** 1.0  
**最後更新:** 2026-02-02  
**狀態:** 已實作 (Implemented)

## 1. 概述 (Overview)
人員使用率 (User Utilization) 是一個關鍵指標，定義為 **活躍使用者 (Active Users)** (實際執行任務的人員) 與 **配置使用者 (Config Users)** (系統中設定/授權的人員) 的比率。

$$ \text{人員使用率 (User Utilization)} = \frac{\text{活躍使用者 (Active Users)}}{\text{配置使用者 (Config Users)}} \times 100\% $$

本文件詳細說明了從 Bronze、Silver、Gold 到 Cube.js 各層級的技術實作細節。

---

## 2. 架構資料流 (Architecture Data Flow)

```mermaid
graph TD
    subgraph "MSSQL 來源 (APP_SRV_COMMON)"
        S1[EmpNodeRoleMapping]
        S2[UserGroup]
        S3[ProcessRoleUserMapping]
        S4[EmpOrgInfoMapping]
    end

    subgraph "Bronze 層 (ClickHouse)"
        B1[common_emp_node_role_mapping]
        B2[common_user_group]
        B3[common_process_role_user_mapping]
        B4[common_emp_org_info_mapping]
        B5[common_flowable_task_stats]
    end

    subgraph "Silver 層 (邏輯視圖)"
        SL1[dim_config_users] -->|驅動表: V1/V2/V3 + 白名單| B1 & B2 & B4
        SL2[mv_fact_task_vx] -->|活躍紀錄| B5
        SL3[mv_dim_mfg_five_level] -->|層級關聯| SL2
    end

    subgraph "Gold 層 (聚合計算)"
        G1[rmv_user_utilization] -->|Cross Join (配置 x 日期) + Left Join (活躍)| SL1 & SL2
    end

    subgraph "服務層 (Serving Layer)"
        C1[Cube.js: UserUtilization] --> G1
        Superset --> C1
    end

    S1 -->|JDBC Sync| B1
    S2 -->|JDBC Sync| B2
    S3 -->|JDBC Sync| B3
    S4 -->|JDBC Sync| B4
```

---

## 3. 各層實作細節 (Implementation Details by Layer)

### 3.1 Bronze 層 (原始資料)
資料透過 JDBC 從 MSSQL `APP_SRV_COMMON` 同步至 ClickHouse `bronze` 資料庫。

| 表格名稱 | 來源表格 | 更新頻率 | 用途 |
|------------|--------------|------------------|---------|
| `bronze.common_emp_node_role_mapping` | `EmpNodeRoleMapping` | 每日 | 關聯人員與節點 (透過 NodeCode 定義 V1/V2/V3 範圍) |
| `bronze.common_user_group` | `UserGroup` | 每日 | 定義使用者角色 (User, Manager, Admin) |
| `bronze.common_process_role_user_mapping` | `ProcessRoleUserMapping` | 每日 | 定義 白名單/排除名單 (Whitelist/Blacklist) 權限 |
| `bronze.common_emp_org_info_mapping` | `EmpOrgInfoMapping` | 每日 | 映射人員至 Plant/Factory/Region (組織架構) |
| `bronze.common_flowable_task_stats` | `FlowableTaskStats` | 即時 | 人員任務操作紀錄 (Todo/Doing/Done) |

### 3.2 Silver 層 (商業邏輯)

#### A. 配置人員邏輯 (`silver.dim_config_users`)
定義於 `sql/etl/08_silver_config_users.sql`。
*   **目標**: 識別「分母」(誰 *應該* 使用系統？)。
*   **V1/V2/V3 規則**:
    *   解析 `EmpNodeRoleMapping` 中的 `NodeCode` 欄位。
    *   樣式匹配: `V1_` -> V1, `V2_` -> V2, `V3_` -> V3。
*   **角色限制 (Role Constraint)**:
    *   V2/V3: 僅包含 `UserGroupName = 'User'` 的使用者。
    *   V1: 包含所有使用者 (無群組限制)。
*   **權限規則 (Permission Rule)**:
    *   必須存在於 `ProcessRoleUserMapping` (白名單)。
    *   必須不在排除名單中 (Blacklist)。
*   **維度擴展**:
    *   關聯 `EmpOrgInfoMapping` 與 `Five Level Master` 以取得 `Region` (區域), `Factory` (工廠), `Line` (產線) 等資訊。

#### B. 活躍人員邏輯 (`silver.mv_fact_task_vx`)
定義於 `sql/etl/03_silver_layer2.sql`。
*   **目標**: 識別「分子」(誰 *正在* 使用系統？)。
*   **邏輯**:
    *   從 `common_flowable_task_stats` 提取任務資料。
    *   將 `TaskDefinitionKey` 與變數映射至 V1/V2/V3 類型。
    *   狀態: 僅 `DOING` 或 `DONE` 的任務計為「活躍 (Active)」。

### 3.3 Gold 層 (指標聚合)

#### `gold.rmv_user_utilization`
定義於 `sql/etl/09_gold_user_utilization_v2.sql`.

**設計策略: 骨架/驅動表 (Skeleton/Driver Table)**
為了正確計算使用率 (即使當日活躍度為 0 也要有分母)，我們採用 **交叉連接 (Cross Join)** 策略：

1.  **日期骨架 (Date Spine)**: 產生每日的日期列表 (過去 365 天)。
2.  **配置骨架 (Config Skeleton)**: `配置人員 (Config Users)` × `日期 (Dates)`。這建立了每一天的分母基準。
3.  **活躍關聯 (Active Association)**: 將 `活躍人員 (Active Users)` (Log) 左連接 (Left Join) 到骨架上。
4.  **聚合 (Aggregation)**: 依據日期與製造維度進行 Group By。

**Schema:**
*   `snapshot_date`: 資料日期。
*   `region`, `plant`, `factory`, `line`: 製造層級維度。
*   `vx_type`: V1 / V2 / V3。
*   `config_users`: 去重後的授權員工代碼 (emp_codes) 數量。
*   `active_users`: 去重後的活躍員工代碼 (emp_codes) 數量。
*   `utilization_rate`: `active / config * 100`。

**引擎**: `REFRESHABLE MATERIALIZED VIEW` (每 1 小時自動刷新)。

### 3.4 Cube.js 層
定義於 `cube/model/cubes/cube_user_utilization.js`.

**量測指標 (Measures)**:
*   `configUsers`: `config_users` 的加總 (Sum)。
*   `activeUsers`: `active_users` 的加總 (Sum)。
*   `utilizationRate`: 全局比率計算 (`Sum(Active) / Sum(Config)`).
    *   *注意: 比率是在查詢時計算 (Query time)，避免發生平均值的平均 (Simpson's Paradox) 錯誤。*

---

## 4. 維護與驗證 (Maintenance & Validation)

### 驗證查詢 (Validation Queries)
用於驗證資料完整性：
```sql
-- 依 Vx 檢查使用率統計
SELECT vx_type, sum(config_users), sum(active_users) 
FROM gold.rmv_user_utilization 
GROUP BY vx_type;
```

### 常見問題 (Common Issues)
1.  **出現 Unknown Region/Factory**:
    *   原因: `EmpOrgInfoMapping` 中的代碼不存在於主檔 (`common_mdm_mfg_plant_master`)。
    *   解法: 更新主檔數據，或檢查 MSSQL 來源是否有新代碼。
2.  **配置人數 (Config Users) 為 0**:
    *   原因: `NodeCode` 格式變更 (例如從 `V1_` 變成 `V1.`) 導致 Regex 匹配失敗。
    *   解法: 更新 `silver.dim_config_users.sql` 中的 Regex 邏輯。
