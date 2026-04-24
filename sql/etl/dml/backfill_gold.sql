-- Phase 4c (V3): Gold Layer Unified Bitmap Merge
-- 目的: 合併 Milestone 與 ACC 數據，產生最終的金層物理快照
-- 變數: {start_ts}, {end_ts}

INSERT INTO gold.rmv_l5_task_completion_phys
SELECT
    m.snapshot_date,
    m.vx_type, m.region, m.plant, m.factory, m.line,
    -- Total Task: 該維度下所有曾出現過的任務聯集 (Todo | Doing | Done)
    bitmapOr(bitmapOr(m.todo, m.doing), m.done) AS total_task,
    m.todo,
    m.doing,
    m.done,
    a.acc,
    now() AS _refresh_time
FROM (
    SELECT 
        snapshot_date, vx_type, region, plant, factory, line,
        groupBitmapMergeState(todo) AS todo,
        groupBitmapMergeState(doing) AS doing,
        groupBitmapMergeState(done) AS done
    FROM gold.rmv_l5_milestone_phys
    WHERE snapshot_date >= toDate('{start_ts}') AND snapshot_date <= toDate('{end_ts}')
    GROUP BY snapshot_date, vx_type, region, plant, factory, line
) AS m
LEFT JOIN (
    SELECT 
        snapshot_date, vx_type, region, plant, factory, line,
        groupBitmapMergeState(acc) AS acc
    FROM gold.rmv_l5_acc_phys
    WHERE snapshot_date >= toDate('{start_ts}') AND snapshot_date <= toDate('{end_ts}')
    GROUP BY snapshot_date, vx_type, region, plant, factory, line
) AS a ON m.snapshot_date = a.snapshot_date 
      AND m.vx_type = a.vx_type 
      AND m.region = a.region 
      AND m.plant = a.plant 
      AND m.factory = a.factory 
      AND m.line = a.line;
