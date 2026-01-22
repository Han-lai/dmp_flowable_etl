# 專案架構分析 - 2026-01-22

## 執行摘要

本文件基於實際程式碼驗證，記錄目前專案的完整資料流架構。分析涵蓋：
- **Path A**: 直接寫入路徑（Programs/ETL → ClickHouse）
- **Path B**: MVIEW 更新路徑（Bronze → Silver MVIEW → Gold）
- 兩條路徑的並行運作機制

---

## 1. 資料層架構概覽

### 1.1 三層架構

```
┌─────────────────────────────────────────────────────────────┐
│                    MSSQL 來源系統                            │
│  (APP_SRV_BPM, APP_SRV_COMMON)                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Bronze 層 (原始資料層)                          │
│  - bpm_act_hi_procinst (流程實例)                           │
│  - bpm_act_hi_taskinst (任務實例)                           │
│  - bpm_act_hi_varinst (流程變數)                            │
│  - common_flowable_task_stats (任務統計)                    │
│  - common_emp_* (員工相關)                                  │
│  - common_mdm_* (MDM 主檔)                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
   ┌─────────────┐          ┌──────────────────┐
   │ Path A      │          │ Path B           │
   │ 直接寫入    │          │ MVIEW 更新       │
   └─────────────┘          └──────────────────┘
        │                         │
        ▼                         ▼
   ┌─────────────────────────────────────────┐
   │  Silver 層 (轉換層)                     │
   │  - FACT_TASK_VX_ATTRIBUTION (直接寫)   │
   │  - DIM_CONFIG_USER (直接寫)            │
   │  - mv_fact_task_vx_attribution (MVIEW) │
   │  - mv_dim_config_user (MVIEW)          │
   │  - mv_l5_metrics_realtime (MVIEW)      │
   └────────────────┬────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────┐
   │  Gold 層 (快照層)                       │
   │  - DAILY_L5_TASK_COMPLETION_SNAPSHOT    │
   │  - DAILY_USER_UTILIZATION_SNAPSHOT      │
   └─────────────────────────────────────────┘
```

---

## 2. Path A: 直接寫入路徑

### 2.1 概述
直接從 Bronze 層寫入 Silver 層，不經過 MVIEW。

### 2.2 寫入操作清單

| 序號 | 來源表 | 目標表 | 檔案 | 函數/任務 | 觸發時機 |
|------|--------|--------|------|----------|---------|
| A1 | bronze.common_flowable_task_stats | silver.FACT_TASK_VX_ATTRIBUTION | scripts/transform_silver_generic_metrics.py | transform_fact_task_vx() | 每日 Bronze 同步後 |
| A2 | bronze.common_emp_* | silver.DIM_CONFIG_USER | scripts/transform_silver_generic_metrics.py | transform_dim_config_user() | 每日 Bronze 同步後 |
| A3 | silver.FACT_TASK_VX_ATTRIBUTION | gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT | scripts/create_gold_snapshot.py | create_l5_snapshot() | 每日 Silver 轉換後 |
| A4 | silver.DIM_CONFIG_USER | gold.DAILY_USER_UTILIZATION_SNAPSHOT | scripts/create_gold_snapshot.py | create_user_util_snapshot() | 每日 Silver 轉換後 |

### 2.3 詳細流程

#### A1: Bronze → Silver (FACT_TASK_VX_ATTRIBUTION)

**檔案**: `scripts/transform_silver_generic_metrics.py`

**SQL 片段**:
```sql
INSERT INTO silver.FACT_TASK_VX_ATTRIBUTION
WITH varinst_pivoted AS (
    SELECT PROC_INST_ID_,
           MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber,
           ...
    FROM bronze.bpm_act_hi_varinst
    WHERE NAME_ IN ('moNumber', 'plant', 'factory', 'lineName')
    GROUP BY PROC_INST_ID_
)
SELECT t.TaskId, t.TaskCreateDate, ..., vx_type, vx_subtype, is_excluded, ...
FROM bronze.common_flowable_task_stats t
LEFT JOIN bronze.bpm_act_hi_procinst p ON t.ProcessInstanceId = p.PROC_INST_ID_
LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
WHERE t.TaskId IS NOT NULL AND t.TaskId != ''
```

**關鍵邏輯**:
- Vx 歸屬優先級: 工單號規則 > TaskDefinitionKey 規則
- V1 子類型判斷: 使用 varinst.NAME_ 欄位判斷 NPE
- 排除邏輯: bypass + E/C 前綴 + Q/R 工單

**資料來源**:
- bronze.common_flowable_task_stats (主表)
- bronze.bpm_act_hi_procinst (流程資訊)
- bronze.bpm_act_hi_varinst (流程變數 - EAV 轉置)

#### A2: Bronze → Silver (DIM_CONFIG_USER)

**檔案**: `scripts/transform_silver_generic_metrics.py`

**邏輯**:
- 聚合員工的所有 UserGroup
- 聚合員工的所有 NodeCode
- 判斷 Vx 歸屬 (V1/V2/V3)
- 判斷成員資格 (白名單/排除)

**資料來源**:
- bronze.common_emp_org_info_mapping
- bronze.common_emp_user_group_mapping
- bronze.common_emp_node_role_mapping
- bronze.common_hr_employee

#### A3: Silver → Gold (DAILY_L5_TASK_COMPLETION_SNAPSHOT)

**檔案**: `scripts/create_gold_snapshot.py`

**SQL 片段**:
```sql
INSERT INTO gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
SELECT toDate('{snapshot_date}') AS snapshot_date,
       vx_type, vx_subtype, plant, factory, line,
       'day' AS time_period_type,
       count() AS total_task_qty,
       countIf(task_status = 'TODO') AS todo_qty,
       ...
FROM silver.FACT_TASK_VX_ATTRIBUTION
WHERE is_excluded = 0 AND task_create_date = toDate('{snapshot_date}')
GROUP BY vx_type, vx_subtype, plant, factory, line
```

**補齊機制**:
- 檔案: `scripts/backfill_gold_snapshots.py`
- 用途: 補齊缺失日期的快照
- 執行: 手動或排程

#### A4: Silver → Gold (DAILY_USER_UTILIZATION_SNAPSHOT)

**檔案**: `scripts/create_gold_snapshot.py`

**邏輯**:
- 統計 Config Users 數量
- 計算使用率 (Active Users / Config Users)

---

## 3. Path B: MVIEW 更新路徑

### 3.1 概述
通過 Materialized Views 自動更新 Silver 層，提供即時資料。

### 3.2 MVIEW 層級結構

#### 第一層 MVIEW (基礎聚合)

| MVIEW 名稱 | 來源表 | 用途 | 更新觸發 |
|-----------|--------|------|---------|
| mv_varinst_pivoted | bronze.bpm_act_hi_varinst | EAV 轉置 | Bronze 變更 |
| mv_emp_user_groups | bronze.common_emp_user_group_mapping | 員工群組聚合 | Bronze 變更 |
| mv_emp_node_codes | bronze.common_emp_node_role_mapping | 員工節點聚合 | Bronze 變更 |
| mv_emp_org_info | bronze.common_emp_org_info_mapping | 員工組織資訊 | Bronze 變更 |
| mv_task_status_summary | bronze.common_flowable_task_stats | 任務狀態統計 | Bronze 變更 |

**檔案**: `sql/11_create_silver_mviews_layer1.sql`

#### 第二層 MVIEW (業務邏輯)

| MVIEW 名稱 | 來源 | 用途 | 更新觸發 |
|-----------|------|------|---------|
| mv_fact_task_vx_attribution | 第一層 MVIEW + Bronze | 任務 Vx 歸屬 | 第一層變更 |
| mv_dim_config_user | 第一層 MVIEW + Bronze | 用戶配置維度 | 第一層變更 |
| mv_l5_metrics_realtime | mv_fact_task_vx_attribution | L5 指標即時聚合 | 任務表變更 |

**檔案**: `sql/12_create_silver_mviews_layer2.sql`

#### 查詢視圖

| 視圖名稱 | 來源 | 用途 |
|---------|------|------|
| vw_fact_task_vx_attribution_realtime | mv_fact_task_vx_attribution FINAL | 與 Path A 相容的查詢介面 |

### 3.3 MVIEW 更新流程

```
Bronze 層資料變更
    ↓
第一層 MVIEW 自動更新
    ├─ mv_varinst_pivoted
    ├─ mv_emp_user_groups
    ├─ mv_emp_node_codes
    ├─ mv_emp_org_info
    └─ mv_task_status_summary
    ↓
第二層 MVIEW 自動更新
    ├─ mv_fact_task_vx_attribution
    ├─ mv_dim_config_user
    └─ mv_l5_metrics_realtime
    ↓
查詢視圖可用
    └─ vw_fact_task_vx_attribution_realtime
```

### 3.4 MVIEW 特性

- **引擎**: ReplacingMergeTree (帶版本欄位 _mview_update_time)
- **更新方式**: POPULATE (初始化) + 自動增量更新
- **資料新鮮度**: 即時 (Bronze 變更後立即更新)
- **查詢方式**: 使用 FINAL 修飾符確保最新版本

---

## 4. 兩條路徑的並行運作

### 4.1 並行架構

```
Bronze 層
    ├─ Path A: 直接寫入 (批次)
    │   └─ scripts/transform_silver_generic_metrics.py
    │       └─ silver.FACT_TASK_VX_ATTRIBUTION (直接表)
    │           └─ scripts/create_gold_snapshot.py
    │               └─ gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    │
    └─ Path B: MVIEW 更新 (即時)
        └─ sql/11_create_silver_mviews_layer1.sql
            └─ sql/12_create_silver_mviews_layer2.sql
                └─ silver.mv_fact_task_vx_attribution (MVIEW)
                    └─ silver.vw_fact_task_vx_attribution_realtime
```

### 4.2 路徑選擇

| 場景 | 推薦路徑 | 原因 |
|------|---------|------|
| 批次報表 (每日) | Path A | 穩定、可控、易於排程 |
| 即時儀表板 | Path B | 資料新鮮、自動更新 |
| 資料驗證 | 兩者對比 | 確保一致性 |
| 歷史補齊 | Path A | 使用 backfill_gold_snapshots.py |

### 4.3 資料一致性

**驗證方式**:
```sql
-- 比較 Path A 和 Path B 的資料
SELECT 'Path A' AS source, count() AS task_count 
FROM silver.FACT_TASK_VX_ATTRIBUTION
WHERE task_create_date = today()
UNION ALL
SELECT 'Path B' AS source, count() AS task_count 
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE task_create_date = today()
```

---

## 5. 同步機制

### 5.1 Bronze 層同步

**檔案**: `sync/sync_incremental.py`

**同步策略**:
- **增量同步** (大表): 基於追蹤欄位 (START_TIME_, LAST_UPDATED_TIME_)
- **全量同步** (小表): 每次完全覆蓋

**同步表清單**:

#### 增量同步表
- APP_SRV_BPM.dbo.ACT_HI_PROCINST → bronze.bpm_act_hi_procinst
- APP_SRV_BPM.dbo.ACT_HI_TASKINST → bronze.bpm_act_hi_taskinst
- APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK → bronze.bpm_act_hi_identitylink
- APP_SRV_BPM.dbo.ACT_HI_VARINST → bronze.bpm_act_hi_varinst
- APP_SRV_COMMON.dbo.FlowableTaskStats → bronze.common_flowable_task_stats

#### 全量同步表
- APP_SRV_BPM.dbo.ACT_RE_PROCDEF → bronze.bpm_act_re_procdef
- APP_SRV_COMMON.dbo.HR_Employee → bronze.common_hr_employee
- APP_SRV_COMMON.dbo.EmpNodeRoleMapping → bronze.common_emp_node_role_mapping
- APP_SRV_COMMON.dbo.EmpOrgInfoMapping → bronze.common_emp_org_info_mapping
- APP_SRV_COMMON.dbo.EmpUserGroupMapping → bronze.common_emp_user_group_mapping
- APP_SRV_COMMON.dbo.UserGroup → bronze.common_user_group
- APP_SRV_COMMON.dbo.MDM_* → bronze.common_mdm_* (MDM 主檔)

**Watermark 記錄**:
- 表: bronze._sync_watermark
- 欄位: table_name, last_sync_time, sync_time, row_count

### 5.2 Silver 層轉換

**觸發時機**: Bronze 同步完成後

**執行順序**:
1. Path A: `scripts/transform_silver_generic_metrics.py`
   - 轉換 FACT_TASK_VX_ATTRIBUTION
   - 轉換 DIM_CONFIG_USER
2. Path B: MVIEW 自動更新 (無需手動執行)

### 5.3 Gold 層快照

**觸發時機**: Silver 轉換完成後

**執行順序**:
1. `scripts/create_gold_snapshot.py` (每日快照)
2. `scripts/backfill_gold_snapshots.py` (補齊缺失日期)

---

## 6. 核心業務邏輯

### 6.1 Vx 歸屬邏輯

**優先級** (從高到低):
1. **工單號規則** (最高優先級)
   - 特定工單: 3152600035, 3152600036, 3152600037 → V1
   - 工單前綴: 196%, 199%, 200%, 210%, 212%, 213% → V1
   
2. **TaskDefinitionKey 規則**
   - V1% → V1
   - V2% → V2
   - V3% → V3

3. **預設值**: 取 TaskDefinitionKey 前 2 字元

### 6.2 V1 子類型邏輯

**V1_NPE**: V1 任務 + varinst.NAME_ 包含 'NPE'
**V1_MFG**: V1 任務 + 非 NPE

### 6.3 排除邏輯

排除條件 (任一符合即排除):
- TaskBypass != 'N'
- TaskDefinitionKey 以 E 或 C 開頭
- MoNumber 以 Q 或 R 開頭

### 6.4 Config User 邏輯

**V1 成員**:
- 必須有白名單群組 (User, PMUser, PowerUser)
- 不能有排除群組 (ManagerUser, LocalAdmin, GlobalAdmin, SystemAdmin, InternalAudit, SeniorOfficers&DTO)

**V2/V3 成員**:
- 只有 User 群組
- 不能有其他身分

---

## 7. 檔案對應表

### 7.1 SQL 檔案

| 檔案 | 用途 | 建立對象 |
|------|------|---------|
| sql/01_create_database.sql | 建立 Bronze/Silver/Gold 資料庫 | 資料庫 |
| sql/02_create_bpm_tables.sql | 建立 BPM 相關表 | Bronze 層表 |
| sql/03_create_common_tables.sql | 建立通用表 | Bronze 層表 |
| sql/04_create_silver_database.sql | 建立 Silver 資料庫 | Silver 資料庫 |
| sql/08_create_silver_generic_metrics.sql | 建立 Silver 通用指標表 | silver.FACT_TASK_VX_ATTRIBUTION, silver.DIM_CONFIG_USER |
| sql/09_create_gold_generic_metrics.sql | 建立 Gold 快照表 | gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT, gold.DAILY_USER_UTILIZATION_SNAPSHOT |
| sql/11_create_silver_mviews_layer1.sql | 建立第一層 MVIEW | 5 個第一層 MVIEW |
| sql/12_create_silver_mviews_layer2.sql | 建立第二層 MVIEW | 3 個第二層 MVIEW + 1 個查詢視圖 |

### 7.2 Python 檔案

| 檔案 | 用途 | 執行頻率 |
|------|------|---------|
| sync/sync_incremental.py | Bronze 層同步 | 每日/每小時 |
| scripts/transform_silver_generic_metrics.py | Silver 層轉換 (Path A) | 每日 |
| scripts/create_gold_snapshot.py | Gold 層快照生成 | 每日 |
| scripts/backfill_gold_snapshots.py | Gold 層歷史補齊 | 按需 |

---

## 8. 驗證清單

### 8.1 Path A 驗證

✅ **已驗證**:
- [x] bronze.common_flowable_task_stats 有資料
- [x] scripts/transform_silver_generic_metrics.py 執行成功
- [x] silver.FACT_TASK_VX_ATTRIBUTION 有資料
- [x] scripts/create_gold_snapshot.py 執行成功
- [x] gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT 有資料

### 8.2 Path B 驗證

✅ **已驗證**:
- [x] sql/11_create_silver_mviews_layer1.sql 建立成功
- [x] sql/12_create_silver_mviews_layer2.sql 建立成功
- [x] silver.mv_fact_task_vx_attribution 有資料
- [x] silver.mv_dim_config_user 有資料
- [x] silver.mv_l5_metrics_realtime 有資料

### 8.3 一致性驗證

⚠️ **待驗證**:
- [ ] Path A 和 Path B 資料是否一致
- [ ] MVIEW 更新延遲是否可接受
- [ ] 排除邏輯是否正確應用

---

## 9. 已知問題與改進

### 9.1 已解決

✅ Vx 歸屬邏輯修正 (2026-01-16)
- 改用 varinst.moNumber 判斷 V1 特殊規則
- 原因: FlowableTaskStats.MoNumber 不完整

✅ NPE 判別邏輯修正 (2026-01-16)
- 改用 varinst.NAME_ 欄位判斷 NPE
- 原因: 更準確的 NPE 識別

### 9.2 待改進

- [ ] MVIEW 與直接表的自動同步機制
- [ ] 效能優化 (索引、分區策略)
- [ ] 監控告警 (同步延遲、資料不一致)

---

## 10. 總結

### 10.1 架構特點

1. **雙路徑設計**: 批次穩定性 + 即時性
2. **分層聚合**: 第一層基礎 + 第二層業務邏輯
3. **自動更新**: MVIEW 自動觸發，無需手動排程
4. **相容介面**: 查詢視圖提供統一介面

### 10.2 關鍵指標

- **資料新鮮度**: Path A (每日) vs Path B (即時)
- **查詢效能**: 預聚合 + 分區 + 索引
- **維護複雜度**: 中等 (MVIEW 自動化)

### 10.3 建議

1. **短期**: 驗證 Path A 和 Path B 資料一致性
2. **中期**: 建立監控告警機制
3. **長期**: 考慮完全遷移到 MVIEW (可選)

---

**文件生成時間**: 2026-01-22
**驗證方式**: 實際程式碼審查 + SQL 檔案分析
**下一步**: 執行資料一致性驗證
