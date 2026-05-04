# DMP Flowable 業務指標與數據定義 (Business Metrics & Data Definitions)

**文件編號**: 03-MTR-001  
**最後更新**: 2026-04-30  
**狀態**: 正式發布 (Released)  
**維護者**: AIT / Data Engineering  
**定位**: 本文件為系統的業務語義辭典，記載 L5 任務指標的精確定義、演進歷程、五階維度血緣與查帳對齊基準。ETL 技術執行細節（SQL 邏輯、管線階段）請見 `02_02_ETL_Transformation_Pipeline.md`。

---

## 1. 核心指標定義 (Core Metrics Definitions)

L5 報表核心圍繞「任務狀態」與「所在時間區間」進行多維度拆解。

### 1.1 任務狀態與時間顆粒 (Status & Time Granularity)
報表固定展示以下六種項目 (Item)，**不可新增或調整順序**：

| Item 項目 | 說明與計算邏輯 (週期感知結算邏輯) |
| :--- | :--- |
| **Total Task** | 該開單日 (`task_start_date`) 產生的任務總數。所有時間粒度的分母基準一致。 |
| **Todo** | **結算點尚未被領取**的任務。依報表粒度不同，結算點分別為：<br>● **日**: 開單當天 23:59:59<br>● **週**: 該 ISO 週週日 23:59:59<br>● **月**: 該曆月底 23:59:59 |
| **Doing** | **結算點已被領取但未完工**的任務。 |
| **Done** | **結算點已經結案**的任務。 |
| **Doing + Done** | 該週期結算點有進度的任務 (分子)。 |
| **Todo + Doing (Acc)** | **累積在途量 (Accumulated WIP)**：採 7 天滑動視窗。從開單日起算 7 天內，截至基準日(D)尚未結案的任務總數 (跨日追蹤)。 |

### 1.2 週期結算邊界 (Temporal Evaluation Boundaries)
系統採用「週期感知」邏輯，會根據查詢的粒度自動擴展結算範圍，解決跨年/跨月數據斷層問題：

| 報表粒度 | 結算時間點 (Evaluation Point) | 數據範圍感知 |
| :--- | :--- | :--- |
| **Daily** | 當日 23:59:59 | 僅包含開單當天完成的數量。 |
| **Weekly** | **該週週日 23:59:59** | 自動包含 12/29~01/04 (W1) 的跨年完成任務。 |
| **Monthly** | **該月最後一秒 23:59:59** | 結算至 12/31 23:59:59 的最終狀態。 |

### 1.3 動態時間欄位解析 (Dynamic Time Columns)
報表提供跨日、跨週、跨月的動態時序追蹤：

| 欄位名稱 (Pattern) | 說明與動態邏輯 |
| :--- | :--- |
| **Month (`MMM`)** | 計算篩選月份（自然月 1 號至月底）內的任務數與比例。 |
| **W44 (`W${x}`)** | **當月最大週次**。若查詢「當前月」，x 為今日所屬週次；若查詢「歷史月」，x 為該月最後一日所屬週次。若該週未結束，僅統計已發生日期。 |
| **W43 (`W${x}-1`)** | 前一完整週 (Mon ~ Sun) 的數據。 |
| **W42 (`W${x}-2`)** | 前兩完整週 (Mon ~ Sun) 的數據。 |
| **Dn-1 ~ Dn-7** | 基準日逐日往前推 7 天。**注意**：此處的比率分母為 *該日的 7 天滑動總量 (Total Task Rolling 7D)*，以解決週末任務量偏低導致比例暴增的失真問題。 |

---

## 2. 重大邏輯修正紀錄 (Logic Revision History)

本節保留了系統指標邏輯重要分水嶺，供後續查帳與邏輯追溯。

### 2.1 跨年週期對齊與多粒度結算 (2026-04-29)
針對跨年對帳落差與週/月結算邏輯不一的問題，進行終極重構：

1.  **跨年對帳對齊 (Year-End Alignment)**
    *   **問題**：W1 (12/29~01/04) 的任務在舊系統中會被 12/31 切斷，導致 TODO/DONE 數量與 MSSQL 不符。
    *   **修正**：實作「週期感知」查詢。當查詢 W1 時，系統會自動將結算邊界延伸至 01/04，確保達成 TODO: 12 / DONE: 440 的原始對齊。
2.  **雙軌年份設計 (Dual-Year Indexing)**
    *   Gold 層導入 `calendar_year` (曆年) 與 `iso_year` (ISO週年)。
    *   **月報表**：篩選 `calendar_year`，確保包含 12/29-12/31。
    *   **週報表**：篩選 `iso_year`，確保 W1 數據完整呈現。
3.  **多粒度結算 Bitmap (Multi-Granularity Bitmaps)**
    *   物理表儲存 `_daily`, `_weekly`, `_monthly` 三套 Bitmap，預先計算不同邊界下的狀態，達成秒級響應。

### 2.2 任務歸屬對齊與互斥狀態計算 (2026-04-28)
針對前期數據重疊與狀態漏接問題，全面實作任務歸屬對齊邏輯：

1.  **任務歸屬對齊 (Task Attribution & Mutually Exclusive)**
    *   **變更前**：任務狀態依據時間快照展開，可能在同一天內被同時標記為 Todo 與 Doing。
    *   **變更後**：強制將所有指標綁定在「開單日 (`task_start_date`)」上，並保證 Todo、Doing、Done 百分之百互斥 (加總等於 Total Task)。
2.  **SYSTEM 帳號全域排除 (System Bypass)**
    *   新增 Bypass 規則：只要執行者為 `SYSTEM`，全面標記為 `is_excluded = 1` (`exclude_reason = 'system_bypass'`) 並剔除於分母外。
3.  **NULL 與預設日期補償 (Null Date Compensation)**
    *   修復 ClickHouse 將未結案任務的 `END_TIME_` 轉為 `1970-01-01` 導致全數誤判為 Done 的問題。
    *   修復 `CLAIM_TIME_` 為 NULL 時掉出 Todo/Doing 判定框的缺陷 (利用 `COALESCE` 補償)。

### 2.3 時點快照與 Vx 歸屬邏輯確立 (2026-02-04)
針對前期數據不一致，確立了以下四大核心機制：

1.  **Vx 歸屬優先級確立 (Vx Attribution Priority)**
    *   **變更前**：工單號規則 (315%) 優先，導致跨流程誤判。
    *   **變更後**：**優先判斷 TaskDefinitionKey 前綴** (V1/V2/V3)。僅在 TaskDef 無法判定時，才套用工單號 (moNumber) 輔助歸屬。
2.  **時點快照狀態 (Point-in-time Status)**
    *   **變更前**：使用任務「目前最新狀態」統計歷史數據，導致昨日的報表今日看會變動。
    *   **變更後改採動態比對**：
        *   Todo：`snapshot_date < CLAIM_TIME_`
        *   Doing：`snapshot_date >= CLAIM_TIME_ AND snapshot_date < END_TIME_`
        *   Done：`snapshot_date >= END_TIME_`
3.  **累積在途量 (Acc) 滾動邏輯**
    *   由「單日 Todo+Doing」改為真實反映工作負擔的 **7 天滑動活動視窗 (Rolling 7-Day Activity)**。
4.  **Triple-OR 篩選邏輯 (Robust Filtering)**
    *   任務過濾條件精確化：`(START_TIME_ OR CLAIM_TIME_ OR END_TIME_) BETWEEN dates`，確保該週期內沾到邊的任務皆不漏傳。

---

## 3. 製造五階與資料血緣 (Data Lineage Mapping)

本節定義了 L5 報表核心維度：**製造五階 (Region → Vx → Plant → Factory → Line)** 的來源與推導邏輯。

### 3.1 維度串接核心理念
*   **來源雙重保障**：以 Flowable 原生變數表 (`ACT_HI_VARINST`) 為主，若缺失則以公用主檔 (`APP_SRV_COMMON.dbo.MDM_*`) 補齊。
*   **實作位置**：`silver.mv_fact_task_vx`。

### 3.2 五階推導邏輯速查

| 階層 | 欄位 | 主要來源 (VARINST 優先) | 備用來源 (MDM 補齊) | 備註 |
| :--- | :--- | :--- | :--- | :--- |
| **1. 區域** | `region` | `varinst_region` | `mdm_region` (透過 factory 串接) | 如 CNE |
| **2. 流程** | `vx_type` | `TaskDefinitionKey` | `moNumber` 前綴 | 分為 V1/V2/V3 |
| **3. 廠區** | `plant` | `varinst_plant` | `mdm_plant` (Business Key 推導) | 如 WJ2 |
| **4. 工廠** | `factory` | `varinst_factory` | `mdm_factory` | 如 NBU |
| **5. 產線** | `line` | `varinst_line` | `mdm_line` | 如 E5 |

*程式碼實現示意:*
```sql
COALESCE(NULLIF(vd.varinst_region, ''), md.mdm_region) AS region
```

---

## 4. 前端明細表欄位對照 (UI Detail Fields Mapping)



所有欄位皆已實作於 `cube/model/cubes/cube_l5_task_details.js`，可直接供 Superset 或 API 查詢使用。

### 4.1 識別與流程資訊

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

### 4.2 時間軸

| 業務名稱 (Display Name) | Cube 欄位名 | 來源欄位 | 備註 |
| :--- | :--- | :--- | :--- |
| **開單日期** | `taskStartDate` | `task_start_date` | 任務被觸發的日期 (Date) |
| **簽收日期** | `taskClaimDate` | `task_claim_date` | 人員點擊認領的日期 |
| **完成日期** | `taskEndDate` | `task_end_date` | 任務結案的日期 |
| **開單時間** | — | `task_start_time` | 完整時間戳記 (DateTime) |
| **接單時間** | — | `task_claim_time` | 已過濾 1970 假日期 |
| **完工時間** | — | `task_end_time` | 任務完工時間戳記 |

### 4.3 狀態結算 (對齊 KPI Cube)

| 業務名稱 (Display Name) | Cube 欄位名 | 說明 |
| :--- | :--- | :--- |
| **日結算狀態** | `statusDaily` | 開單當日 23:59 結算 → 對應 KPI Cube 的 `todo_daily/doing_daily/done_daily` |
| **週結算狀態** | `statusWeekly` | 開單週的週日 23:59 結算 → 對應 KPI Cube 的 `todo_weekly/doing_weekly/done_weekly` |
| **月結算狀態** | `statusMonthly` | 開單月的月底 23:59 結算 → 對應 KPI Cube 的 `todo_monthly/doing_monthly/done_monthly` |

### 4.4 製造維度

| 業務名稱 (Display Name) | Cube 欄位名 | 範例值 |
| :--- | :--- | :--- |
| **業務分類** | `vxType` | V1 / V2 / V3 |
| **區域** | `region` | CNE |
| **廠別** | `plant` | WJ2 |
| **工廠** | `factory` | NBU |
| **線別** | `line` | E5 |

### 4.5 業務擴充變數 (全量 11 欄)

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

### 4.6 效能指標

| 業務名稱 (Display Name) | Cube 欄位名 | 計算邏輯 |
| :--- | :--- | :--- |
| **總持續時間 (分鐘)** | `durationMin` | `(task_end_time - task_start_time) / 60` |
| **實際處理時間 (分鐘)** | `processingTimeMin` | `(task_end_time - task_claim_time) / 60` |

---

## 5. 明細架構說明 (Detail Implementation Architecture)

### 5.1 資料流架構

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

### 5.2 設計原則

*   **KPI 與明細解耦**：`L5TaskDetails` 為純明細模型，不做時間序列聚合。所有 KPI 指標請使用 `L5TaskPeriodic` Cube。
*   **去重保障**：使用 `FINAL` 關鍵字確保從 ReplacingMergeTree 讀取去重後的唯一版本，避免重複明細。
*   **自動排除**：查詢時自動過濾 `is_excluded = 1` 的系統自動任務（如 SYSTEM 帳號、autoComplete 節點）。
*   **業務變數與人員來源**：業務擴充變數（工單號、機種等）與人員姓名（HR 關聯）皆已在 Silver 層 ETL 過程中透過 `backfill_silver.sql` 合併，不需在查詢時另行 JOIN。



---

**相關文件**:
- 完整管線執行細節 → `02_02_ETL_Transformation_Pipeline.md`
- 查帳與驗證指南 → `03_Detailed_Audit_Guide.md`
- SQL 原始模板 → `sql/etl/dml/backfill_*.sql`

---

**文件負責人**: AIT / Data Engineering
**最後審核日期**: 2026-04-30
