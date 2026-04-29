-- Phase 5: Gold Milestone Table (Task Completion KPI)
-- 目的：將事實表數據進行預聚合，使用 Bitmap 儲存 Task ID 以實現極速的去重統計與維度鑽取
-- 商業意義：提供日/週/月報表的 TODO/DOING/DONE 核心指標，支持跨時間粒度的數據對齊
-- 變數: {start_ts}, {end_ts}

INSERT INTO gold.rmv_l5_milestone_phys
SELECT
    -- [1. 快照與維度]
    task_start_date AS snapshot_date,
    vx_type, region, plant, factory, line,
    
    -- [2. Daily Metrics: 結算於開單日當天]
    -- todo_daily: 尚未被領取的任務 (claim_date > 當天 或 為空)
    groupBitmapStateIf(cityHash64(task_id), 
        COALESCE(task_claim_date, toDate('1900-01-01')) != task_start_date 
        AND (task_end_date IS NULL OR task_end_date != task_start_date)
    ) AS todo_daily,
    -- doing_daily: 當天領取且尚未完成的任務
    groupBitmapStateIf(cityHash64(task_id), 
        task_claim_date = task_start_date 
        AND (task_end_date IS NULL OR task_end_date != task_start_date)
    ) AS doing_daily,
    -- done_daily: 當天完成的任務
    groupBitmapStateIf(cityHash64(task_id), 
        task_end_date = task_start_date
    ) AS done_daily,

    -- [3. Weekly Metrics: 結算於開單日所在週的週日]
    -- todo_weekly: 週內未被領取的任務
    groupBitmapStateIf(cityHash64(task_id), 
        (task_claim_date IS NULL OR task_claim_date > (toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY))
        AND (task_end_date IS NULL OR task_end_date > (toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY))
    ) AS todo_weekly,
    -- doing_weekly: 週內已領取但尚未完成的任務
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

    -- [New] 週期標籤
    toYear(task_start_date) AS calendar_year,
    toISOYear(task_start_date) AS iso_year,
    toISOWeek(task_start_date) AS iso_week,
    toMonth(task_start_date) AS iso_month,

    now() AS _refresh_time
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND task_start_date >= toDate('{start_ts}')
  AND task_start_date <= toDate('{end_ts}')
GROUP BY snapshot_date, calendar_year, iso_year, iso_week, iso_month, vx_type, region, plant, factory, line;
