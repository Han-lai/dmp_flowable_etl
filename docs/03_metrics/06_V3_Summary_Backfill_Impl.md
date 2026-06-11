# L5 指標雙管線架構說明

> **文件位置**：`docs/03_metrics/06_V3_Summary_Backfill_Impl.md`  
> **最後更新**：2026-06-11  
> **前置閱讀**：[05_Calculation_Logic_Changelog.md](05_Calculation_Logic_Changelog.md)

---

## 目錄

1. [架構總覽](#1-架構總覽)
2. [V3 管線（≤ 2026-03-31）](#2-v3-管線--2026-03-31)
3. [V4 管線（≥ 2026-04-01）](#3-v4-管線--2026-04-01)
4. [共用輸出層](#4-共用輸出層)
5. [邊界注意事項](#5-邊界注意事項)
6. [維運操作](#6-維運操作)

---

## 1. 架構總覽

L5 指標採**雙管線架構**，以 `2026-04-01` 為固定分界：

| 時間範圍 | 管線 | SQL 入口 | 計算典範 |
|---------|------|---------|---------|
| **≤ 2026-03-31** | **V3 管線** | `backfill_summary_v3.sql` | 事件日快照（混合） |
| **≥ 2026-04-01** | **V4 管線** | `backfill_gold_summary.sql` | 開單日 Cohort |

兩條管線**各司其職、互不干擾**，最終都寫入同一張預聚合彙總表，Cube.js 直接讀取。

> **重要**：兩條管線**都只讀取 Silver 資料，從不修改它**。所有計算差異完全發生在 Gold 層。Silver 資料由獨立的 Bronze → Silver ETL 維護，V3/V4 管線不介入。

```
Bronze → Silver ETL（獨立維護，V3/V4 不觸及）
     │
     ↓
Silver (mv_fact_task_vx)   ← V3/V4 管線只 SELECT，從不 INSERT/UPDATE
     │
     ├── [V3 管線] SELECT，task_start_date ≤ 2026-03-31
     │   backfill_summary_v3.sql
     │   ├─ Day:   事件日 ARRAY JOIN；acc 另讀 gold.rmv_l5_acc_phys（見註）
     │   ├─ Week:  Cohort + ISO 週鍵（toISOYear=toYear 排除跨年 Dec 29-31）
     │   └─ Month: Cohort 月底截面
     │
     └── [V4 管線] SELECT，task_start_date ≥ 2026-04-01
         backfill_gold_milestone.sql  →  gold.rmv_l5_task_completion_phys (Bitmap)
         backfill_gold_acc.sql        →  gold.rmv_l5_acc_phys (Bitmap)  ← V3 Day acc 也讀此表
         backfill_gold_summary.sql    →  解碼整數
                                                  │
                                                  ↓
                                     gold.rmv_l5_task_summary
                                     （ReplacingMergeTree，兩管線共用）
                                                  │
                                     Cube.js cube_l5_task_periodic.js
                                     （sum() 查詢）
```

> **註：V3 Day acc 的 Gold 層依賴**  
> V3 管線的 Day acc（積壓率分子）讀取 `gold.rmv_l5_acc_phys`，此表由 V4 的 `backfill_gold_acc.sql` 寫入，且**無 V3/V4 邊界限制**，因此 ≤ 2026-03 的 acc 資料也存在其中。  
> 這是 Gold 層之間的單向依賴：V3 summary 依賴 V4 acc，但兩者都不回寫 Silver。

---

## 2. V3 管線（≤ 2026-03-31）

### 2.1 為什麼 V3 需要獨立管線

V4 管線的計算起點是「**任務開單日**」（task_start_date），一個任務對應一筆快照。  
但 2026-03 以前的歷史資料，業務上習慣以「**事件發生日**」來看每天的任務狀態——同一任務在開單日、領單日、結案日各出現一次，呈現狀態流動。  
若直接用 V4 邏輯回填歷史資料，Done Rate 會從 ~65% 驟降至 ~20%，與歷史觀測值不符。

V3 管線保留了這套事件日快照語意，作為歷史資料的正式計算來源。

### 2.2 V3 各粒度計算邏輯

| 粒度 | snapshot_date 定義 | todo / doing / done 條件 | acc 來源 |
|------|-------------------|--------------------------|---------|
| **Day** | ARRAY JOIN `[task_start_date, task_claim_date, task_end_date]` | 以 snapshot_date 相對各事件日判斷當天狀態 | `rmv_l5_acc_phys` 7D 滾動 Bitmap |
| **Week** | `task_start_date`（Cohort） | 以 ISO 週末（`week_end = toStartOfWeek + 6d`）為結算截面 | `todo_qty + doing_qty`（等於 total − done） |
| **Month** | `task_start_date`（Cohort） | 以月底（`toLastDayOfMonth`）為結算截面 | 同上 |

> Week/Month 採用 Cohort 語意（與 V4 相同），而非事件日展開，原因：
> 週/月維度下事件日會造成大量重複計數（同一任務可能跨週/月出現多次），Cohort 語意才能得到穩定的「當週/當月有多少任務待處理」數字。

### 2.3 跨年週處理（Dec 29-31）

ISO 週規則下，12/29~12/31 可能屬於下一年的第 1 週（如 2025-12-31 → 2026-W01）。  
V3 管線加入 `toISOYear(task_start_date) = toYear(task_start_date)` 過濾，這些任務不計入任何週彙總，避免跨年汙染。

### 2.4 SQL 檔案

`sql/etl/dml/backfill_summary_v3.sql`  
邊界保護：`AND snapshot_date < toDate('2026-04-01')`（無論傳入的日期範圍為何，永遠不會寫入 4 月以後的資料）

---

## 3. V4 管線（≥ 2026-04-01）

### 3.1 計算典範

以「**任務開單日**」（task_start_date）為唯一快照點，狀態在以下截面評估：

| 粒度 | 結算截面 | 狀態語意 |
|------|---------|---------|
| **Day** | 每個 snapshot_date | 當天開單且當天符合條件的任務 |
| **Week** | `toStartOfWeek + 6d`（ISO 週末） | 週末截面的 Bitmap 狀態 |
| **Month** | `toLastDayOfMonth` | 月底截面的 Bitmap 狀態 |

歷史數字一旦計算完成**永不改變**，不隨後續任務進度漂移。

### 3.2 管線步驟

```
1. backfill_gold_milestone.sql
   → gold.rmv_l5_task_completion_phys（含 Day/Week/Month Bitmap 欄位）

2. backfill_gold_acc.sql
   → gold.rmv_l5_acc_phys（7 天滾動視窗 acc Bitmap）

3. backfill_gold_summary.sql
   → 讀 Bitmap 表，解碼為整數後寫入 gold.rmv_l5_task_summary
```

### 3.3 邊界保護

`backfill_gold_summary.sql` 加入 `AND snapshot_date >= toDate('2026-04-01')`，  
即使傳入 `--start 2025-10-08` 也不會寫入 3 月以前的資料，V3 資料不會被覆蓋。

---

## 4. 共用輸出層

### 4.1 表結構

```sql
gold.rmv_l5_task_summary
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (period_type, vx_type, period_key, region, plant, factory, line)
```

- 同一 `(period_type, vx_type, period_key, region, plant, factory, line)` 組合，查詢時加 `FINAL` 自動保留 `_refresh_time` 最新的一筆。
- 兩條管線寫入的 key 範圍天然不重疊（V3 寫 ≤ 2026-03，V4 寫 ≥ 2026-04），正常情況下不會互相覆蓋。

### 4.2 Cube.js 查詢

`cube/model/cubes/cube_l5_task_periodic.js` 直接對 `gold.rmv_l5_task_summary FINAL` 執行 `sum()`，不區分資料來自哪條管線。

---

## 5. 邊界注意事項

### 5.1 2026-03 / 2026-04 邊界斷層

兩條管線計算語意不同，邊界月份的趨勢圖**會出現合理落差**：

| 月份 | 管線 | Done Rate 典型範圍 | 原因 |
|------|------|------------------|------|
| 2026-03 | V3（事件日） | ~60-70% | Done 包含所有歷史結案事件快照 |
| 2026-04 | V4（開單日） | ~20-35% | Done 僅計當月開單且當月結案的任務 |

建議在儀表板於 2026-04-01 附近加上「計算邏輯切換」標示。

### 5.2 跨邊界任務

2026-03-28 開單、2026-04-05 結案的任務：
- **V3 管線**：3 月 Week/Month 計為 Todo；4 月的事件日（結案日）計為 Done
- **V4 管線**：完全歸屬開單日 3/28，在 4 月統計中**不出現**（task_start_date 在邊界之前）

此為預期行為，無需修正。

---

## 6. 維運操作

### 6.1 管線整合方式

兩條管線透過 `scripts/etl/config/pipeline_config.yaml` 整合進同一個 `execute_etl.py`，以兩個連續 step 執行：

```yaml
- phase_id: "gold_summary_v3"
  template: "backfill_summary_v3.sql"       # V3 管線：自帶 < 2026-04-01 邊界保護
- phase_id: "gold_summary"
  template: "backfill_gold_summary.sql"     # V4 管線：自帶 >= 2026-04-01 邊界保護
```

兩支 SQL 各自的 WHERE 條件天然隔離，不需要 Python 層做任何日期判斷。  
傳入任何日期範圍，每支 SQL 只寫入自己負責的區間，另一區間安靜跳過。

### 6.2 日常增量 ETL

```powershell
# 自動接龍（依 Watermark 補齊落差）
python scripts/etl/execute_etl.py --daily
```

增量模式的起點由 `phase = 'gold_summary'` 的 checkpoint 決定，通常只跑當天（≥ 2026-04-01），`gold_summary_v3` step 會因 WHERE 條件為空自動跳過，不寫入任何資料。

### 6.3 回填 V3 歷史資料（首次或 Silver 修正後）

```powershell
# 完整回填 2025-10-08 ~ 2026-03-31
python scripts/etl/execute_etl.py --backfill --start 2025-10-08 --end 2026-03-31

# 只重算特定月份
python scripts/etl/execute_etl.py --backfill --start 2025-12-01 --end 2025-12-31
```

### 6.4 回填 V4 歷史資料

```powershell
# 重算 V4 管線某段日期
python scripts/etl/execute_etl.py --backfill --start 2026-04-01 --end 2026-05-31
```

### 6.4 驗證查詢

```sql
-- 確認 V3/V4 邊界兩側資料是否存在
SELECT
    CASE WHEN snapshot_date < toDate('2026-04-01') THEN 'V3 期間' ELSE 'V4 期間' END AS pipeline,
    period_type,
    min(snapshot_date) AS min_date,
    max(snapshot_date) AS max_date,
    count() AS rows
FROM gold.rmv_l5_task_summary FINAL
GROUP BY pipeline, period_type
ORDER BY pipeline, period_type;

-- 確認無重複 key（ReplacingMergeTree OPTIMIZE 是否完成）
SELECT period_type, period_key, vx_type, region, plant, factory, line,
       count() AS cnt
FROM gold.rmv_l5_task_summary
WHERE snapshot_date BETWEEN toDate('2025-12-01') AND toDate('2025-12-31')
GROUP BY period_type, period_key, vx_type, region, plant, factory, line
HAVING cnt > 1
LIMIT 5;
-- 預期：0 rows
```
