-- Phase 4b (V4.1 Cohort 版): Gold Layer ACC Aggregation (Same-day Cohort WIP)
-- 目的: 統計「過去 7 天內新開單，且目前尚未結案」的任務總數
-- 邏輯說明: 透過 ARRAY JOIN 將任務存續期間展開 (Rolling Window)，以計算每日當下的 WIP 負荷量
-- 變數: {start_ts}, {end_ts}

INSERT INTO gold.rmv_l5_acc_phys
SELECT
    toDate(active_date_raw) AS snapshot_date,
    vx_type, region, plant, factory, line,
    -- acc: 7 日內開單且「在該 snapshot_date 尚未結案」的任務
    groupBitmapStateIf(cityHash64(task_id), task_end_date IS NULL OR task_end_date > toDate(active_date_raw)) AS acc,
    -- acc_total_task: 只要是在 7 日內開單的任務 (不管結案了沒)
    groupBitmapState(cityHash64(task_id)) AS acc_total_task,
    -- [New] 週期標籤
    toYear(snapshot_date) AS calendar_year,
    toISOYear(snapshot_date) AS iso_year,
    toISOWeek(snapshot_date) AS iso_week,
    toMonth(snapshot_date) AS iso_month,
    now() AS _refresh_time
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayDistinct(
    -- 重要：這裡要固定展開 7 天，不受到 task_end_date 限制
    range(toUInt32(task_start_date), toUInt32(task_start_date + 7))
) AS active_date_raw
WHERE is_excluded = 0
  AND toDate(active_date_raw) >= toDate('{start_ts}')
  AND toDate(active_date_raw) <= toDate('{end_ts}')
GROUP BY snapshot_date, calendar_year, iso_year, iso_week, iso_month, vx_type, region, plant, factory, line;

