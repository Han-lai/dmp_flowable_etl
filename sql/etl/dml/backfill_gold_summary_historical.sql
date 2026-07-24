-- V3 混合版本：Silver → gold.rmv_l5_task_summary 直通管線
-- 目的: 為 <= 2026-03-31 的期間提供彙總數字
-- 邊界: 此 SQL 僅應對 task_start_date / snapshot_date < '2026-04-01' 的範圍執行
-- 變數: {start_ts}, {end_ts}
--
-- [Changelog]
-- 2026-06-10 (V3.1 混合架構):
--   重構三個粒度策略，解決日/週/月語意不一致與跨年週問題。
--   Day   → 事件日 ARRAY JOIN (event-day countIf)，acc 來自 rmv_l5_acc_phys 7D 滾動
--   Week  → Cohort (task_start_date 為快照，狀態在 ISO 週末評估)
--           加 toISOYear=toYear 過濾，排除 Dec 29-31 跨年任務使其不計入 2026-W01
--           週指標驗證: W51=502/31, W52=583/46, W01=12/5 (total/acc)
--   Month → Cohort (task_start_date 為快照，狀態在月底評估)
--           月指標驗證: Dec total=2294, todo=12, doing=93, done=2189
--   Week/Month acc = todo+doing (cohort 語意下互斥，等於 total-done)
--   Day acc = rmv_l5_acc_phys 7D Rolling Bitmap（與 V4 Day 一致）

INSERT INTO gold.rmv_l5_task_summary

-- ============================================================
-- Day 粒度：事件日 ARRAY JOIN
-- acc 來源：rmv_l5_acc_phys（7 天滑動視窗 Bitmap）
-- ============================================================
WITH acc_day AS (
    SELECT
        snapshot_date,
        vx_type, region, plant, factory, line,
        bitmapCardinality(groupBitmapMergeState(acc))            AS acc_qty,
        bitmapCardinality(groupBitmapMergeState(acc_total_task)) AS acc_total_qty
    FROM gold.rmv_l5_acc_phys
    WHERE snapshot_date >= toDate('{start_ts}')
      AND snapshot_date <= toDate('{end_ts}')
    GROUP BY snapshot_date, vx_type, region, plant, factory, line
)
SELECT
    'Day'                       AS period_type,
    toString(snapshot_date)     AS period_key,
    snapshot_date,
    0                           AS sort_order,
    toString(snapshot_date)     AS period_name,
    vx_type, region, plant, factory, line,
    uniqExact(task_id)          AS total_qty,
    countIf(snapshot_date < COALESCE(task_claim_date, task_end_date, today() + 1))
                                AS todo_qty,
    countIf(
        task_claim_date IS NOT NULL
        AND snapshot_date >= task_claim_date
        AND (task_end_date IS NULL OR snapshot_date < task_end_date)
    )                           AS doing_qty,
    countIf(task_end_date IS NOT NULL AND snapshot_date >= task_end_date)
                                AS done_qty,
    countIf(
        (task_claim_date IS NOT NULL
         AND snapshot_date >= task_claim_date
         AND (task_end_date IS NULL OR snapshot_date < task_end_date))
        OR
        (task_end_date IS NOT NULL AND snapshot_date >= task_end_date)
    )                           AS doing_done_qty,
    any(coalesce(ad.acc_qty,       0)) AS acc_qty,
    any(coalesce(ad.acc_total_qty, 0)) AS acc_total_qty,
    now64(3)                    AS _refresh_time
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayDistinct(arrayFilter(
    d -> d IS NOT NULL,
    [task_start_date, task_claim_date, task_end_date]
)) AS snapshot_date
LEFT JOIN acc_day AS ad USING (snapshot_date, vx_type, region, plant, factory, line)
WHERE is_excluded = 0
  AND snapshot_date >= toDate('{start_ts}')
  AND snapshot_date <= toDate('{end_ts}')
  AND snapshot_date < toDate('2026-04-01')
GROUP BY snapshot_date, vx_type, region, plant, factory, line

UNION ALL

-- ============================================================
-- Week 粒度：Cohort（與 V4 backfill_gold_milestone.sql 相同語意）
--   snapshot_date = task_start_date
--   week_end      = toStartOfWeek(task_start_date, 3) + 6 天
--   period_key    = ISO 年週 (toISOYear / toISOWeek)
-- ============================================================
SELECT
    period_type, period_key, max_snap AS snapshot_date,
    sort_order, period_name,
    vx_type, region, plant, factory, line,
    total_qty, todo_qty, doing_qty, done_qty, doing_done_qty,
    acc_qty, acc_total_qty, _refresh_time
FROM (
    WITH toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY AS week_end
    SELECT
        'Week'                  AS period_type,
        concat(toString(toISOYear(task_start_date)), '-W',
               lpad(toString(toISOWeek(task_start_date)), 2, '0'))
                                AS period_key,
        max(task_start_date)    AS max_snap,
        0                       AS sort_order,
        concat('W', toString(toISOWeek(task_start_date)))
                                AS period_name,
        vx_type, region, plant, factory, line,
        count()                 AS total_qty,
        countIf(
            (task_claim_date IS NULL OR task_claim_date > week_end)
            AND (task_end_date IS NULL OR task_end_date > week_end)
        )                       AS todo_qty,
        countIf(
            task_claim_date IS NOT NULL AND task_claim_date <= week_end
            AND (task_end_date IS NULL OR task_end_date > week_end)
        )                       AS doing_qty,
        countIf(task_end_date IS NOT NULL AND task_end_date <= week_end)
                                AS done_qty,
        countIf(
            (task_claim_date IS NOT NULL AND task_claim_date <= week_end
             AND (task_end_date IS NULL OR task_end_date > week_end))
            OR
            (task_end_date IS NOT NULL AND task_end_date <= week_end)
        )                       AS doing_done_qty,
        countIf(
            (task_claim_date IS NULL OR task_claim_date > week_end)
            AND (task_end_date IS NULL OR task_end_date > week_end)
        ) + countIf(
            task_claim_date IS NOT NULL AND task_claim_date <= week_end
            AND (task_end_date IS NULL OR task_end_date > week_end)
        )                       AS acc_qty,
        count()                 AS acc_total_qty,
        now64(3)                AS _refresh_time
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0
      AND task_start_date >= toStartOfWeek(toDate('{start_ts}'), 3)
      AND task_start_date <= toDate('{end_ts}')
      -- 週粒度邊界落在週界而非 04-01：historical 止於 W13(3/29)，W14(3/30~4/5) 整週交 V4，
      -- 避免跨界週被兩側各寫一半而遭 ReplacingMergeTree 覆蓋（見 backfill_gold_summary.sql Week 分支）。
      AND task_start_date < toDate('2026-03-30')
      AND toISOYear(task_start_date) = toYear(task_start_date)
    GROUP BY period_key, period_name, vx_type, region, plant, factory, line
)

UNION ALL

-- ============================================================
-- Month 粒度：Cohort（與 V4 backfill_gold_milestone.sql 相同語意）
--   month_end = toLastDayOfMonth(task_start_date)
-- ============================================================
SELECT
    period_type, period_key, max_snap AS snapshot_date,
    sort_order, period_name,
    vx_type, region, plant, factory, line,
    total_qty, todo_qty, doing_qty, done_qty, doing_done_qty,
    acc_qty, acc_total_qty, _refresh_time
FROM (
    WITH toLastDayOfMonth(task_start_date) AS month_end
    SELECT
        'Month'                 AS period_type,
        formatDateTime(task_start_date, '%Y-%m')
                                AS period_key,
        max(task_start_date)    AS max_snap,
        0                       AS sort_order,
        formatDateTime(toStartOfMonth(task_start_date), '%b.')
                                AS period_name,
        vx_type, region, plant, factory, line,
        count()                 AS total_qty,
        countIf(
            (task_claim_date IS NULL OR task_claim_date > month_end)
            AND (task_end_date IS NULL OR task_end_date > month_end)
        )                       AS todo_qty,
        countIf(
            task_claim_date IS NOT NULL AND task_claim_date <= month_end
            AND (task_end_date IS NULL OR task_end_date > month_end)
        )                       AS doing_qty,
        countIf(task_end_date IS NOT NULL AND task_end_date <= month_end)
                                AS done_qty,
        countIf(
            (task_claim_date IS NOT NULL AND task_claim_date <= month_end
             AND (task_end_date IS NULL OR task_end_date > month_end))
            OR
            (task_end_date IS NOT NULL AND task_end_date <= month_end)
        )                       AS doing_done_qty,
        countIf(
            (task_claim_date IS NULL OR task_claim_date > month_end)
            AND (task_end_date IS NULL OR task_end_date > month_end)
        ) + countIf(
            task_claim_date IS NOT NULL AND task_claim_date <= month_end
            AND (task_end_date IS NULL OR task_end_date > month_end)
        )                       AS acc_qty,
        count()                 AS acc_total_qty,
        now64(3)                AS _refresh_time
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0
      AND task_start_date >= toStartOfMonth(toDate('{start_ts}'))
      AND task_start_date <= toDate('{end_ts}')
      AND task_start_date < toDate('2026-04-01')
    GROUP BY period_key, period_name, vx_type, region, plant, factory, line
);
