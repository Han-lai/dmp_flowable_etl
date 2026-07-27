-- Phase 4d: Gold Layer Pre-computed Summary (方案 C 優化)
-- 目的: 將 bitmap merge 計算移至 ETL 階段，Cube 查詢只做整數 SUM
-- 效能: 查詢從 ~750ms 降至 ~184ms (-75%)
-- 變數: {start_ts}, {end_ts}
--
-- [重要] 版本邊界保護：
--   此 SQL 僅處理 >= 2026-04-01 的資料（V4.3 Cohort 邏輯）
--   <= 2026-03-31 的資料由 backfill_gold_summary_historical.sql 負責（V3 Bitmap 邏輯）
--   若 {end_ts} < 2026-04-01，此 SQL 將不寫入任何資料（WHERE 條件自然為空）

-- Day 粒度: 每日一行，直接計算
INSERT INTO gold.rmv_l5_task_summary
SELECT
    'Day' AS period_type,
    toString(snapshot_date) AS period_key,
    snapshot_date,
    0 AS sort_order,
    toString(snapshot_date) AS period_name,
    vx_type, region, plant, factory, line,
    groupBitmapMerge(total_task) AS total_qty,
    groupBitmapMerge(todo_daily) AS todo_qty,
    groupBitmapMerge(doing_daily) AS doing_qty,
    groupBitmapMerge(done_daily) AS done_qty,
    bitmapCardinality(bitmapOr(
        groupBitmapMergeState(doing_daily),
        groupBitmapMergeState(done_daily)
    )) AS doing_done_qty,
    groupBitmapMerge(acc) AS acc_qty,
    groupBitmapMerge(acc_total_task) AS acc_total_qty,
    now64(3) AS _refresh_time
FROM gold.rmv_l5_task_completion_phys
WHERE snapshot_date >= toDate('{start_ts}')
  AND snapshot_date <= toDate('{end_ts}')
  AND snapshot_date >= toDate('2026-04-01')   -- V3/V4 邊界保護
GROUP BY snapshot_date, vx_type, region, plant, factory, line

UNION ALL

-- Day 粒度補丁: acc_phys 有記錄但當天無任務（total=0）的日期（如假日、停產日）
-- 目的: 確保 acc 積壓數在零開單日仍可查詢，不依賴前端補 0
SELECT
    'Day' AS period_type,
    toString(a.snapshot_date) AS period_key,
    a.snapshot_date,
    0 AS sort_order,
    toString(a.snapshot_date) AS period_name,
    a.vx_type, a.region, a.plant, a.factory, a.line,
    0 AS total_qty,
    0 AS todo_qty,
    0 AS doing_qty,
    0 AS done_qty,
    0 AS doing_done_qty,
    bitmapCardinality(a.acc)            AS acc_qty,
    bitmapCardinality(a.acc_total_task) AS acc_total_qty,
    now64(3) AS _refresh_time
FROM gold.rmv_l5_acc_phys AS a FINAL
LEFT ANTI JOIN (
    SELECT DISTINCT snapshot_date, vx_type, region, plant, factory, line
    FROM gold.rmv_l5_task_completion_phys
    WHERE snapshot_date >= toDate('{start_ts}')
      AND snapshot_date <= toDate('{end_ts}')
      AND snapshot_date >= toDate('2026-04-01')
) AS c
ON  a.snapshot_date = c.snapshot_date
AND a.vx_type   = c.vx_type
AND a.region    = c.region
AND a.plant     = c.plant
AND a.factory   = c.factory
AND a.line      = c.line
WHERE a.snapshot_date >= toDate('{start_ts}')
  AND a.snapshot_date <= toDate('{end_ts}')
  AND a.snapshot_date >= toDate('2026-04-01')

UNION ALL

-- Week 粒度: 按 ISO 週聚合
SELECT
    'Week' AS period_type,
    concat(toString(toISOYear(snapshot_date)), '-W',
           lpad(toString(toISOWeek(snapshot_date)), 2, '0')) AS period_key,
    max(snapshot_date) AS max_snap_dt,
    0 AS sort_order,
    concat('W', toString(toISOWeek(snapshot_date))) AS period_name,
    vx_type, region, plant, factory, line,
    groupBitmapMerge(total_task) AS total_qty,
    groupBitmapMerge(todo_weekly) AS todo_qty,
    groupBitmapMerge(doing_weekly) AS doing_qty,
    groupBitmapMerge(done_weekly) AS done_qty,
    bitmapCardinality(bitmapOr(
        groupBitmapMergeState(doing_weekly),
        groupBitmapMergeState(done_weekly)
    )) AS doing_done_qty,
    bitmapCardinality(bitmapOr(
        groupBitmapMergeState(todo_weekly),
        groupBitmapMergeState(doing_weekly)
    )) AS acc_qty,
    groupBitmapMerge(acc_total_task) AS acc_total_qty,
    now64(3) AS _refresh_time
FROM gold.rmv_l5_task_completion_phys
WHERE snapshot_date >= toStartOfWeek(toDate('{start_ts}'), 3)
  AND snapshot_date <= toStartOfWeek(toDate('{end_ts}'), 3) + INTERVAL 6 DAY
  AND snapshot_date >= toDate('2026-03-30')   -- 2026-W14 週一
GROUP BY period_key, period_name, vx_type, region, plant, factory, line

UNION ALL

-- Month 粒度: 按月聚合
SELECT
    'Month' AS period_type,
    formatDateTime(snapshot_date, '%Y-%m') AS period_key,
    max(snapshot_date) AS max_snap_dt,
    0 AS sort_order,
    formatDateTime(toStartOfMonth(snapshot_date), '%b.') AS period_name,
    vx_type, region, plant, factory, line,
    groupBitmapMerge(total_task) AS total_qty,
    groupBitmapMerge(todo_monthly) AS todo_qty,
    groupBitmapMerge(doing_monthly) AS doing_qty,
    groupBitmapMerge(done_monthly) AS done_qty,
    bitmapCardinality(bitmapOr(
        groupBitmapMergeState(doing_monthly),
        groupBitmapMergeState(done_monthly)
    )) AS doing_done_qty,
    bitmapCardinality(bitmapOr(
        groupBitmapMergeState(todo_monthly),
        groupBitmapMergeState(doing_monthly)
    )) AS acc_qty,
    groupBitmapMerge(acc_total_task) AS acc_total_qty,
    now64(3) AS _refresh_time
FROM gold.rmv_l5_task_completion_phys
WHERE snapshot_date >= toStartOfMonth(toDate('{start_ts}'))
  AND snapshot_date <= toLastDayOfMonth(toDate('{end_ts}'))
  AND snapshot_date >= toDate('2026-04-01')   -- V3/V4 邊界保護
GROUP BY period_key, period_name, vx_type, region, plant, factory, line;
