-- Phase 4c (V4.2 Cohort 版): Gold Layer Final Aggregation (Activity Mode)
-- 目的: 合併 Milestone 與 ACC 資料至最終物理表
-- 變數: {start_ts}, {end_ts}

INSERT INTO gold.rmv_l5_task_completion_phys
SELECT
    m.snapshot_date,
    m.vx_type, m.region, m.plant, m.factory, m.line,
    bitmapOr(bitmapOr(m.todo_daily, m.doing_daily), m.done_daily) AS total_task,
    m.todo_daily,
    m.doing_daily,
    m.done_daily,
    m.todo_weekly,
    m.doing_weekly,
    m.done_weekly,
    m.todo_monthly,
    m.doing_monthly,
    m.done_monthly,
    a.acc,
    now() AS _refresh_time
FROM gold.rmv_l5_milestone_phys AS m
LEFT JOIN gold.rmv_l5_acc_phys AS a 
    ON m.snapshot_date = a.snapshot_date 
    AND m.vx_type = a.vx_type 
    AND m.region = a.region 
    AND m.plant = a.plant 
    AND m.factory = a.factory 
    AND m.line = a.line
WHERE m.snapshot_date >= toDate('{start_ts}')
  AND m.snapshot_date <= toDate('{end_ts}');
