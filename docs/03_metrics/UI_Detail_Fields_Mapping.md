# DMP Flowable 前端明細表欄位對照指南 (UI Detail Fields Mapping)

**文件編號**: 03-MTR-002  
**最後更新**: 2026-04-30  
**狀態**: 正式發布 (Released)  
**維護者**: AIT / Data Engineering

**文件定位**: 本文件說明「業務/前端畫面需求明細欄位」與「Cube.js `L5TaskDetails` 模型欄位」的映射關係。明細功能透過 Cube.js Semantic Layer 提供，底層資料來源為 `silver.mv_fact_task_vx FINAL`。

---

## 🟢 1. 已實作欄位總覽 (透過 L5TaskDetails Cube 提供)

所有欄位皆已實作於 `cube/model/cubes/cube_l5_task_details.js`，可直接供 Superset 或 API 查詢使用。

### 1.1 識別與流程資訊

| 業務名稱 (Display Name) | Cube 欄位名 | 來源欄位 | 備註 |
| :--- | :--- | :--- | :--- |
| **任務 ID** | `taskId` | `task_id` | Flowable 原生 ID，設為 Primary Key |
| **流程實例 ID** | `procInstId` | `proc_inst_id` | 一張工單下所有節點共享同一 ID |
| **任務定義 Key** | `taskDefinitionKey` | `task_definition_key` | 例如 `V3_Task_01`，用於分辨業務節點 |
| **任務名稱** | `taskName` | `task_name` | 節點前台顯示名稱 |
| **處理人代碼** | `assigneeCode` | `assignee_code` | 系統中的 `ASSIGNEE_` 帳號/工號 |
| **處理人姓名** | `assigneeName` | `assignee_name` | 透過 HR 系統轉換的中文姓名 |
| **L4 流程 ID** | `l4ProcessId` | `l4_process_id` | 來源：`ACT_HI_PROCINST.BUSINESS_STATUS_` |
| **L4 流程名稱** | `l4ProcessName` | `l4_process_name` | 來源：`ACT_HI_PROCDEF.NAME_` |

### 1.2 時間軸

| 業務名稱 (Display Name) | Cube 欄位名 | 來源欄位 | 備註 |
| :--- | :--- | :--- | :--- |
| **開單日期** | `taskStartDate` | `task_start_date` | 任務被觸發的日期 (Date) |
| **簽收日期** | `taskClaimDate` | `task_claim_date` | 人員點擊認領的日期 |
| **完成日期** | `taskEndDate` | `task_end_date` | 任務結案的日期 |
| **開單時間** | — | `task_start_time` | 完整時間戳記 (DateTime) |
| **接單時間** | — | `task_claim_time` | 已過濾 1970 假日期 |
| **完工時間** | — | `task_end_time` | 任務完工時間戳記 |

### 1.3 狀態結算 (對齊 KPI Cube)

| 業務名稱 (Display Name) | Cube 欄位名 | 說明 |
| :--- | :--- | :--- |
| **日結算狀態** | `statusDaily` | 開單當日 23:59 結算 → 對應 KPI Cube 的 `todo_daily/doing_daily/done_daily` |
| **週結算狀態** | `statusWeekly` | 開單週的週日 23:59 結算 → 對應 KPI Cube 的 `todo_weekly/doing_weekly/done_weekly` |
| **月結算狀態** | `statusMonthly` | 開單月的月底 23:59 結算 → 對應 KPI Cube 的 `todo_monthly/doing_monthly/done_monthly` |

### 1.4 製造維度

| 業務名稱 (Display Name) | Cube 欄位名 | 範例值 |
| :--- | :--- | :--- |
| **業務分類** | `vxType` | V1 / V2 / V3 |
| **區域** | `region` | CNE |
| **廠別** | `plant` | WJ2 |
| **工廠** | `factory` | NBU |
| **線別** | `line` | E5 |

### 1.5 業務擴充變數 (全量 11 欄)

| 業務名稱 (Display Name) | Cube 欄位名 | 來源變數 (NAME_) |
| :--- | :--- | :--- |
| **工單號** | `moNumber` | `moNumber` |
| **機種** | `modelName` | `modelName` |
| **交付區域** | `deliveryArea` | `deliveryArea` |
| **排程編號** | `scheduleNumber` | `scheduleNumber` |
| **SAP 廠別** | `sapPlant` | `sapPlant` |
| **SAP 產品組** | `sapProductGroup` | `sapProductGroup` |
| **棧板編號** | `pallet` | `pallet` |
| **轉單編號** | `transferNo` | `transferNo` |
| **Q-Block 事件 ID** | `qblockEventId` | `qBlockEventId` |
| **不良品 SN** | `defectSn` | `defectSn` |

### 1.6 效能指標

| 業務名稱 (Display Name) | Cube 欄位名 | 計算邏輯 |
| :--- | :--- | :--- |
| **總持續時間 (分鐘)** | `durationMin` | `(task_end_time - task_start_time) / 60` |
| **實際處理時間 (分鐘)** | `processingTimeMin` | `(task_end_time - task_claim_time) / 60` |

---

## 🔵 2. 架構說明 (Implementation Architecture)

### 2.1 資料流架構

```
silver.mv_fact_task_vx FINAL
        │
        │  (cube_l5_task_details.js)
        │  WHERE is_excluded = 0
        ▼
Cube.js L5TaskDetails Cube
        │
        ▼
Superset 明細表 / API 下鑽查詢
```

### 2.2 設計原則

*   **KPI 與明細解耦**：`L5TaskDetails` 為純明細模型，不做時間序列聚合。所有 KPI 指標請使用 `L5TaskPeriodic` Cube。
*   **去重保障**：使用 `FINAL` 關鍵字確保從 ReplacingMergeTree 讀取去重後的唯一版本，避免重複明細。
*   **自動排除**：查詢時自動過濾 `is_excluded = 1` 的系統自動任務（如 SYSTEM 帳號、autoComplete 節點）。
*   **業務變數與人員來源**：業務擴充變數（工單號、機種等）與人員姓名（HR 關聯）皆已在 Silver 層 ETL 過程中透過 `backfill_silver.sql` 合併，不需在查詢時另行 JOIN。

---

**相關文件**:
- 底層 Silver 事實表定義 → `sql/etl/schema/04_silver_fact_tasks.sql`
- Cube 模型原始碼 → `cube/model/cubes/cube_l5_task_details.js`
- Cube.js 語義層說明 → `docs/04_serving/CubeJS_Semantic_Layer.md`

---

**文件負責人**: AIT / Data Engineering  
**審核狀態**: 已對照 `cube_l5_task_details.js` 實作欄位逐一校對完成。  
**最後審核日期**: 2026-04-30
