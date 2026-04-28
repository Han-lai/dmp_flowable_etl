# DMP Flowable 業務指標與數據定義 (Business Metrics & Data Definitions)

**文件編號**: 03-MTR-001  
**版本**: 5.2  
**最後更新**: 2026-04-28  
**狀態**: 正式發布 (Released)  
**維護者**: AIT / Data Engineering  
**定位**: 本文件為系統的業務語義辭典，記載 L5 任務指標的精確定義、演進歷程、五階維度血緣與查帳對齊基準。ETL 技術執行細節（SQL 邏輯、管線階段）請見 `docs/03_metrics/ETL_Transformation_Pipeline.md`。

---

## 1. 核心指標定義 (Core Metrics Definitions)

L5 報表核心圍繞「任務狀態」與「所在時間區間」進行多維度拆解。

### 1.1 任務狀態與時間顆粒 (Status & Time Granularity)
報表固定展示以下六種項目 (Item)，**不可新增或調整順序**：

| Item 項目 | 說明與計算邏輯 (V4 Cohort 同梯次邏輯) |
| :--- | :--- |
| **Total Task** | 該開單日 (`task_start_date`) 產生的所有任務總數 (基準分母)。 |
| **Todo** | 開單日當天結束前，**未被認領**且未結案的任務。 |
| **Doing** | 開單日當天結束前，**已被認領**但未結案的任務。 |
| **Done** | 開單日當天結束前，**已經結案**的任務。 |
| **Doing + Done** | 開單日當天有進度的任務 (分子)。 |
| **Todo + Doing (Acc)** | **累積在途量 (Accumulated WIP)**：採 7 天滑動視窗。從開單日起算 7 天內，截至基準日(D)尚未結案的任務總數 (跨日追蹤)。 |

### 1.2 動態時間欄位解析 (Dynamic Time Columns)
報表提供跨日、跨週、跨月的動態時序追蹤：

| 欄位名稱 (Pattern) | 說明與動態邏輯 |
| :--- | :--- |
| **Month (`MMM`)** | 計算篩選月份（自然月 1 號至月底）內的任務數與比例。 |
| **W44 (`W${x}`)** | **當月最大週次**。若查詢「當前月」，x 為今日所屬週次；若查詢「歷史月」，x 為該月最後一日所屬週次。若該週未結束，僅統計已發生日期。 |
| **W43 (`W${x}-1`)** | 前一完整週 (Mon ~ Sun) 的數據。 |
| **W42 (`W${x}-2`)** | 前兩完整週 (Mon ~ Sun) 的數據。 |
| **Dn-1 ~ Dn-7** | 基準日逐日往前推 7 天。**注意**：此處的比率分母為 *該日的 7 天滑動總量 (Total Task Rolling 7D)*，以解決週末任務量偏低導致比例暴增的失真問題。 |

---

## 2. 演進歷程與重大修正 (Evolution & Revisions)

本節保留了系統指標邏輯與時俱進的重要分水嶺，供後續查帳與邏輯追溯。

### 2.2 邏輯修正與優化分水嶺 (2026-04-28 V4 Cohort 核心定調)
針對前期數據重疊與狀態漏接問題，全面導入 V4 Cohort 同梯次邏輯：

1.  **同梯次互斥邏輯 (Same-day Cohort & Mutually Exclusive)**
    *   **變更前**：任務狀態依據時間快照展開，可能在同一天內被同時標記為 Todo 與 Doing。
    *   **變更後**：強制將所有指標綁定在「開單日 (`task_start_date`)」上，並保證 Todo、Doing、Done 百分之百互斥 (加總等於 Total Task)。
2.  **SYSTEM 帳號全域排除 (System Bypass)**
    *   新增 Bypass 規則：只要執行者為 `SYSTEM`，全面標記為 `is_excluded = 1` (`exclude_reason = 'system_bypass'`) 並剔除於分母外。
3.  **NULL 與預設日期補償 (Null Date Compensation)**
    *   修復 ClickHouse 將未結案任務的 `END_TIME_` 轉為 `1970-01-01` 導致全數誤判為 Done 的問題。
    *   修復 `CLAIM_TIME_` 為 NULL 時掉出 Todo/Doing 判定框的缺陷 (利用 `COALESCE` 補償)。

### 2.1 邏輯修正與優化分水嶺 (2026-02-04 核心定調)
針對前期數據不一致，確立了以下四大金律：

1.  **Vx 歸屬優先級反轉 (Vx Attribution Priority)**
    *   **變更前**：工單號規則 (315%) 優先，導致跨流程誤判。
    *   **變更後**：**優先判斷 TaskDefinitionKey 前綴** (V1/V2/V3)。僅在 TaskDef 無法判定時，才套用工單號 (moNumber) 輔助歸屬。（*註：曾在 1/21 短暫將工單號權重拉高，後於此版本校正回歸*）
2.  **時點快照狀態 (Point-in-time Status)**
    *   **變更前**：使用任務「目前最新狀態」統計歷史數據，導致昨日的報表今日看會變動。
    *   **變更後改採動態比對**：
        *   Todo：`snapshot_date < CLAIM_TIME_`
        *   Doing：`snapshot_date >= CLAIM_TIME_ AND snapshot_date < END_TIME_`
        *   Done：`snapshot_date >= END_TIME_`
3.  **累積在途量 (Acc) 滾動邏輯**
    *   由「單日 Todo+Doing」改為真實反映工作負擔的 **7 天滑動活動視窗 (Rolling 7-Day Activity)**。
4.  **Triple-OR 篩選邏輯 (V2 Robust Filtering)**
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

## 4. 查帳對齊基準 (Field Verification Reference)

當前台 (Superset / Excel) 數據與後台 (ClickHouse) 出現落差時的單一真理核對口徑。

### 4.1 核心核對準則

| 落差現象 | 可能原因 | 處理方式 |
| :--- | :--- | :--- |
| 前台數量偏高 | 排除規則未生效 | 確認 `is_excluded = 0` 過濾是否套用；檢查 `SYSTEM`、`dummy`、`bypass`、`Q_order` 等 `exclude_reason` |
| 歷史數字今日看不一樣 | 使用了「目前最新狀態」而非快照 | V4 已全面升級為 Cohort 邏輯，歷史數字應鎖定開單日且不隨時間變動。 |
| 時區偏差 | MSSQL 為 Server Local Time，ClickHouse 預設 UTC | 查詢時加 `toTimeZone(field, 'Asia/Taipei')` 或確認 ETL 中已轉換 |
| Doing 數量異常 | `CLAIM_TIME_` 可能為 Null | V4 已透過 `COALESCE` 將未領取的 `task_claim_date` 轉為 `1900-01-01`，確保正確歸類為 Todo 而非 Doing。 |

### 4.2 Gold 層對帳查詢（Snapshot-based，正式口徑）

> **重要**: Gold 層採用「時點快照」判定狀態。`snapshot_date` 是任務在 Start/Claim/End 三個事件日期上展開的快照，**不等同**於 `silver.mv_fact_task_vx.task_status` 的當前狀態欄位。正式對帳應以 Gold 層為準。

```sql
-- 驗證特定日期下，V3 NBU 各線體的 Todo/Doing/Done 分佈
SELECT
    snapshot_date, vx_type, plant, factory, line,
    total_task, todo_count, doing_count, done_count, acc_todo_doing
FROM gold.rmv_l5_task_completion
WHERE snapshot_date = '2025-12-31'
  AND vx_type = 'V3'
  AND factory = 'NBU'
ORDER BY line;
```

### 4.3 Silver 層輔助查詢（任務清單稽核）

> 此查詢用於稽核特定維度下原始任務清單（非快照），`task_status` 欄位為任務**目前最新狀態**，適合確認資料是否正確寫入 Silver，不適合用於重現歷史報表數字。

```sql
SELECT task_id, task_status, vx_type, plant, factory, line,
       task_start_date, task_claim_date, task_end_date,
       is_excluded, exclude_reason
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND vx_type = 'V3' AND factory = 'NBU'
  AND task_start_date >= '2025-12-01'
  AND task_start_date <= '2025-12-31'
ORDER BY task_start_date DESC
```


## 5. SQL 實作規格參考 (Implementation SQL References)

本節的 SQL 實作細節已整併至 [ETL_Transformation_Pipeline.md](ETL_Transformation_Pipeline.md)，作為唯一維護來源。各主題對應章節如下：

| 主題 | 參考位置 |
| :--- | :--- |
| Vx 版本歸屬判定 SQL | `ETL_Transformation_Pipeline.md` §3.3 |
| 資料排除規則 SQL | `ETL_Transformation_Pipeline.md` §3.5 |
| 快照展開與狀態計算 SQL | `ETL_Transformation_Pipeline.md` §5.2-5.3 |
| ACC 七日滾動 SQL | `ETL_Transformation_Pipeline.md` §6.2 |
| SQL 模板原始碼 | `sql/etl/dml/backfill_*.sql` |

---

**相關文件**:
- 完整管線執行細節 → `docs/03_metrics/ETL_Transformation_Pipeline.md`
- SQL 原始模板 → `sql/etl/dml/backfill_*.sql`

---

**文件負責人**: AIT / Data Engineering
**審核狀態**: §1~§4 已對照程式碼驗證完成；§5 SQL 實作已整併至 ETL_Transformation_Pipeline.md（2026-04-23）。
