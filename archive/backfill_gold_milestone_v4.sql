-- Phase 4a (V4.2修正-含空補償): Gold Layer Milestone Aggregation
-- 目的: 加入 COALESCE 確保 NULL 領取時間也能正確計入 Todo
-- 變數: {start_ts}, {end_ts}

INSERT INTO gold.rmv_l5_milestone_v4_phys
SELECT
    task_start_date AS snapshot_date,
    vx_type, region, plant, factory, line,
    
    -- [1. Todo] 使用 COALESCE 確保 NULL 領取時間被判定為「未領取」，避免掉入 Other
    groupBitmapStateIf(cityHash64(task_id), 
        COALESCE(task_claim_date, toDate('1900-01-01')) != task_start_date 
        AND (task_end_date IS NULL OR task_end_date != task_start_date)
    ) AS todo,

    -- [2. Doing]
    groupBitmapStateIf(cityHash64(task_id), 
        task_claim_date = task_start_date 
        AND (task_end_date IS NULL OR task_end_date != task_start_date)
    ) AS doing,
    
    -- [3. Done]
    groupBitmapStateIf(cityHash64(task_id), 
        task_end_date = task_start_date
    ) AS done,

    now() AS _refresh_time
FROM silver.mv_fact_task_vx_v4 FINAL
WHERE is_excluded = 0
  AND task_start_date >= toDate('{start_ts}')
  AND task_start_date <= toDate('{end_ts}')
GROUP BY snapshot_date, vx_type, region, plant, factory, line;
