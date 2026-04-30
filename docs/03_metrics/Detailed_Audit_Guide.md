# DMP 任務明細稽核指南 (Detailed Audit Guide)

本文件整合了 DMP Flowable 系統的數據稽核原理、操作指南與歷史對帳數據，作為跨系統數據比對的單一事實來源。

---

## 1. 稽核背景與數據原理

本系統採用 **獎牌管線架構 (Medallion Architecture)**，數據經過 Bronze (落地) → Silver (清洗) → Gold (物理化快照) 三層轉換。

### 1.1 金層快照展開機制 (Gold Layer Milestone Expansion)

根據金層實作規格（`sql/etl/dml/backfill_gold_milestone.sql`），每一筆任務會依據其生命週期內的 **三個非 NULL 時間點** 展開為快照列：

| 時間點 | 欄位 | Gold 狀態條件 |
| :--- | :--- | :--- |
| 任務開始 (Start) | `task_start_date` | snapshot_date < COALESCE(claim, end, tomorrow) → **Todo** |
| 任務認領 (Claim) | `task_claim_date` | claim ≤ snapshot_date < end → **Doing** |
| 任務結束 (End) | `task_end_date` | snapshot_date ≥ end → **Done** |

**關鍵特性**：
- Silver 層以 `NULLIF` 將未發生的 claim/end 轉為 `NULL`（非 epoch）。
- Gold 的 ARRAY JOIN 僅在任務有事件的日期建立快照，不對每天都建立。
- 因此同一筆任務在不同快照日可能分別計入 Todo、Doing、Done 三個 Bitmap，週/月彙總為 **各狀態 Bitmap 聯集**，而非各狀態互斥計數。

### 1.2 UI 與 Gold 彙總差異說明

| 彙總粒度 | Gold 計算方式 | UI 計算方式 | 預期行為 |
| :--- | :--- | :--- | :--- |
| **日** | 當日各狀態 Bitmap 計數 | 相同 | 應一致 |
| **週/月** | 週期內各狀態 Bitmap **聯集** | 週期末最終狀態（推測） | **必然差異** |

週/月層級的 Gold Todo/Doing/Acc 遠大於 UI，是因為 Gold 將整個週期內曾處於該狀態的任務全部聯集，而非只看週期末的狀態快照。**日級別的比對才是有效的跨系統驗證基礎。**

> **排除規則與 Vx 分類定義**：ClickHouse 端的完整排除條件（bypass / system_node / Q_order / R_order / notify_task / dummy_task）及 Vx 版本歸屬邏輯，詳見 [ETL_Transformation_Pipeline.md](ETL_Transformation_Pipeline.md) §3.3（Vx）及 §3.5（排除規則）。以下對帳均以 `is_excluded = 0` 為前提。

---

## 2. 稽核工具操作說明

### 方法一：使用 ClickHouse SQL 指令 (快速查詢)

> **注意**：Silver 層透過 `NULLIF(toDate(...), toDate('1970-01-01'))` 將未發生的時間欄位儲存為 `NULL`，查詢條件須使用 `IS NULL` / `IS NOT NULL`。

**查詢 Done（結案）任務**：快照日當天結案的任務。

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

**查詢 Todo（待認領）任務**：快照日當天啟動、尚未認領的任務。

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

**查詢 Doing（進行中）任務**：快照日已認領、尚未結案的任務。

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

**日級別 Gold 計數驗證（一次查三個狀態）**：

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

*文件更新日期: 2026-04-30*
