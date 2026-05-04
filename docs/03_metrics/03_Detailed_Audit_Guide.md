# DMP 任務明細稽核指南 (Detailed Audit Guide)

本文件整合了 DMP Flowable 系統的數據稽核原理、操作指南與歷史對帳數據，作為跨系統數據比對的單一事實來源。

---

## 1. 稽核背景與數據原理

本系統採用 **獎牌管線架構 (Medallion Architecture)**，數據經過 Bronze (落地) → Silver (清洗) → Gold (物理化快照) 三層轉換。

### 1.1 金層同梯次結算機制 (Gold Layer Same-Day Cohort)

根據最新的 V4.3 架構，所有任務狀態結算皆採用 **Same-Day Cohort (同梯次)** 邏輯。這代表：

1. **錨定起點**：所有的任務皆以其開單日 (`task_start_date`) 作為唯一歸屬梯次。
2. **狀態互斥**：在任何時間粒度（日/週/月）下，一個任務在該週期末只會處於 `Todo`、`Doing`、`Done` 的其中「唯一一種」狀態。
   - `Todo` + `Doing` + `Done` = 該梯次總任務數 (`Total`)。
3. **高效去重**：由於採用 ClickHouse Bitmap (例如 `groupBitmapMergeState`)，不僅大幅提升查詢效能，也徹底解決了跨天重複計算的問題。系統已廢棄舊版的 `ARRAY JOIN` 展開邏輯。

### 1.2 UI 與 Gold 彙總對齊說明

| 彙總粒度 | Gold 計算方式 | UI 計算方式 | 預期行為 |
| :--- | :--- | :--- | :--- |
| **日 / 週 / 月** | 依據 `task_start_date` 歸屬梯次，計算各狀態互斥的 Bitmap 基數 (Cardinality) | 以相同的起點日查詢，展示最終生命週期狀態 | **完全一致 (100% Alignment)** |

> **排除規則與 Vx 分類定義**：ClickHouse 端的完整排除條件（bypass / system_node / Q_order / R_order / notify_task / dummy_task）及 Vx 版本歸屬邏輯，詳見 [ETL_Transformation_Pipeline.md](ETL_Transformation_Pipeline.md) §3.3（Vx）及 §3.5（排除規則）。以下對帳均以 `is_excluded = 0` 為前提。

---

## 2. 稽核工具操作說明

### 方法一：使用 ClickHouse SQL 指令 (快速查詢)

> **注意**：Silver 層透過 `NULLIF(toDate(...), toDate('1970-01-01'))` 將未發生的時間欄位儲存為 `NULL`，查詢條件須使用 `IS NULL` / `IS NOT NULL`。所有的過濾條件皆以 `task_start_date` 作為梯次基準（Cohort Date）。

**查詢 Done（已結案）任務**：開單日為該日，且在同一天內完成的任務。

```sql
SELECT
    task_id, task_start_time, task_claim_time, task_end_time,
    task_start_date, task_claim_date, task_end_date, task_primary_date,
    task_create_date, task_status, vx_type,
    region, plant, factory, line,
    region_source, plant_source, factory_source, line_source,
    is_excluded, exclude_reason,
    assignee_code, assignee_name,
    task_definition_key, task_name, mo_number, proc_inst_id,
    _mview_update_time
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3'
  AND task_start_date = '2025-12-25'
  AND task_end_date = '2025-12-25'
ORDER BY task_end_time DESC;
```

**查詢 Todo（待認領）任務**：開單日為該日，但在當天結束前尚未被認領的任務。

```sql
SELECT task_id, task_start_time, task_claim_time, task_end_time,
    task_start_date, task_claim_date, task_end_date, task_primary_date,
    task_create_date, task_status, vx_type,
    region, plant, factory, line,
    region_source, plant_source, factory_source, line_source,
    is_excluded, exclude_reason, assignee_code, assignee_name,
    task_definition_key, task_name, mo_number, proc_inst_id, _mview_update_time
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3'
  AND task_start_date = '2025-12-25'
  AND COALESCE(task_claim_date, toDate('1900-01-01')) != '2025-12-25'
  AND (task_end_date IS NULL OR task_end_date != '2025-12-25')
ORDER BY task_start_time DESC;
```

**查詢 Doing（進行中）任務**：開單日為該日，並在當天已被認領，但當天尚未結案的任務。

```sql
SELECT task_id, task_start_time, task_claim_time, task_end_time,
    task_start_date, task_claim_date, task_end_date, task_primary_date,
    task_create_date, task_status, vx_type,
    region, plant, factory, line,
    region_source, plant_source, factory_source, line_source,
    is_excluded, exclude_reason, assignee_code, assignee_name,
    task_definition_key, task_name, mo_number, proc_inst_id, _mview_update_time
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3'
  AND task_start_date = '2025-12-25'
  AND task_claim_date = '2025-12-25'
  AND (task_end_date IS NULL OR task_end_date != '2025-12-25')
ORDER BY task_claim_time DESC;
```

**日級別 Gold 計數驗證（以同梯次 Cohort 一次查三個互斥狀態）**：

```sql
SELECT
    countIf(task_start_date = '2025-12-25' AND task_end_date = '2025-12-25') AS done,
    countIf(task_start_date = '2025-12-25' AND COALESCE(task_claim_date, toDate('1900-01-01')) != '2025-12-25' AND (task_end_date IS NULL OR task_end_date != '2025-12-25')) AS todo,
    countIf(task_start_date = '2025-12-25' AND task_claim_date = '2025-12-25' AND (task_end_date IS NULL OR task_end_date != '2025-12-25')) AS doing
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3';
```

### 方法二：使用 Python 稽核腳本 (產出完整 CSV)

腳本位址：`scripts/etl/audit_done_details.py`

```bash
# Done（預設）
python scripts/etl/audit_done_details.py --date "2025-12-25" --region CNE --plant WJ2 --factory NBU --line E5 --vx V3

# Todo
python scripts/etl/audit_done_details.py --date "2025-12-25" --region CNE --plant WJ2 --factory NBU --line E5 --vx V3 --status todo

# Doing
python scripts/etl/audit_done_details.py --date "2025-12-25" --region CNE --plant WJ2 --factory NBU --line E5 --vx V3 --status doing

# All（任一時間點觸碰快照日）
python scripts/etl/audit_done_details.py --date "2025-12-25" --region CNE --plant WJ2 --factory NBU --line E5 --vx V3 --status all
```

`--status` 支援 `done`（預設）、`todo`、`doing`、`all`，CSV 輸出至 `scratch/audit_{status}_{region}_{plant}_{factory}_{line}_{date}.csv`。



---

## 3. 查帳對齊基準與異常排查 (Verification Reference)

當前台 (Superset / Excel) 數據與後台 (ClickHouse) 出現落差時的單一真理核對口徑。

### 4.1 核心核對準則

| 落差現象 | 可能原因 | 處理方式 |
| :--- | :--- | :--- |
| 前台數量偏高 | 排除規則未生效 | 確認 `is_excluded = 0` 過濾是否套用；檢查 `SYSTEM`、`dummy`、`bypass`、`Q_order` 等 `exclude_reason` |
| 歷史數字今日看不一樣 | 使用了「目前最新狀態」而非快照 | 系統已全面升級為任務歸屬對齊邏輯，歷史數字應鎖定開單日且不隨時間變動。 |
| 時區偏差 | MSSQL 為 Server Local Time，ClickHouse 預設 UTC | 查詢時加 `toTimeZone(field, 'Asia/Taipei')` 或確認 ETL 中已轉換 |
| Doing 數量異常 | `CLAIM_TIME_` 可能為 Null | V4 已透過 `COALESCE` 將未領取的 `task_claim_date` 轉為 `1900-01-01`，確保正確歸類為 Todo 而非 Doing。 |

### 4.2 Gold 層對帳查詢（Snapshot-based，正式口徑）

> **重要**: Gold 層採用「時點快照」判定狀態。`snapshot_date` 是任務在 Start/Claim/End 三個事件日期上展開的快照，**不等同**於 `silver.mv_fact_task_vx.task_status` 的當前狀態欄位。正式對帳應以 Gold 層為準。

```sql
-- 驗證 W1 (12/29 ~ 01/04) 在結算點 01/04 時的 Todo/Doing/Done 分佈
SELECT
    iso_year, iso_week,
    bitmapCardinality(groupBitmapMergeState(total_task)) as total,
    bitmapCardinality(groupBitmapMergeState(todo_weekly)) as todo,
    bitmapCardinality(groupBitmapMergeState(doing_weekly)) as doing,
    bitmapCardinality(groupBitmapMergeState(done_weekly)) as done
FROM gold.rmv_l5_task_completion
WHERE (iso_year = 2026 AND iso_week = 1)
  AND vx_type = 'V3' AND line = 'E5'
GROUP BY iso_year, iso_week;
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



---

*文件更新日期: 2026-04-30*
