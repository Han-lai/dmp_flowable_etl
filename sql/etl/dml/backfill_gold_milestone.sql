-- Phase 4a (V4.2 同梯次版): Gold Layer Milestone Aggregation
-- 目的: 加入 COALESCE 確保 NULL 領取時間也能正確計入 Todo
-- 變數: {start_ts}, {end_ts}

INSERT INTO gold.rmv_l5_milestone_phys
SELECT
    task_start_date AS snapshot_date,
    vx_type, region, plant, factory, line,
    
    -- [1. Daily Metrics: 結算於開單日當天]
    groupBitmapStateIf(cityHash64(task_id), 
        COALESCE(task_claim_date, toDate('1900-01-01')) != task_start_date 
        AND (task_end_date IS NULL OR task_end_date != task_start_date)
    ) AS todo_daily,

    groupBitmapStateIf(cityHash64(task_id), 
        task_claim_date = task_start_date 
        AND (task_end_date IS NULL OR task_end_date != task_start_date)
    ) AS doing_daily,
    
    groupBitmapStateIf(cityHash64(task_id), 
        task_end_date = task_start_date
    ) AS done_daily,

    -- [2. Weekly Metrics: 結算於開單日所在週的週日]
    -- 修正: 使用 (task_claim_date IS NULL OR ...) 替代 COALESCE > 的寫法
    -- 避免 NULL claim_date 在 todo 和 doing 條件中同時失敗的邊界問題
    groupBitmapStateIf(cityHash64(task_id), 
        (task_claim_date IS NULL OR task_claim_date > (toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY))
        AND (task_end_date IS NULL OR task_end_date > (toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY))
    ) AS todo_weekly,

    groupBitmapStateIf(cityHash64(task_id), 
        task_claim_date IS NOT NULL AND task_claim_date <= (toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY)
        AND (task_end_date IS NULL OR task_end_date > (toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY))
    ) AS doing_weekly,
    
    groupBitmapStateIf(cityHash64(task_id), 
        task_end_date <= (toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY)
    ) AS done_weekly,

    -- [3. Monthly Metrics: 結算於開單日所在月的月底]
    -- 修正: 同 Weekly 邏輯，使用 IS NULL / IS NOT NULL 精確處理
    groupBitmapStateIf(cityHash64(task_id), 
        (task_claim_date IS NULL OR task_claim_date > toLastDayOfMonth(task_start_date))
        AND (task_end_date IS NULL OR task_end_date > toLastDayOfMonth(task_start_date))
    ) AS todo_monthly,

    groupBitmapStateIf(cityHash64(task_id), 
        task_claim_date IS NOT NULL AND task_claim_date <= toLastDayOfMonth(task_start_date)
        AND (task_end_date IS NULL OR task_end_date > toLastDayOfMonth(task_start_date))
    ) AS doing_monthly,
    
    groupBitmapStateIf(cityHash64(task_id), 
        task_end_date <= toLastDayOfMonth(task_start_date)
    ) AS done_monthly,

    now() AS _refresh_time
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND task_start_date >= toDate('{start_ts}')
  AND task_start_date <= toDate('{end_ts}')
GROUP BY snapshot_date, vx_type, region, plant, factory, line;
