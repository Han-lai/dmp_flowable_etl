-- Phase 4a (V3): Gold Layer Milestone Aggregation (Bitmap Version)
-- 目的: 將任務狀態轉化為 Bitmap，支援精確去重與跨維度聚合
-- 變數: {start_ts}, {end_ts}

INSERT INTO gold.rmv_l5_milestone_phys
SELECT
    snapshot_date,
    vx_type, region, plant, factory, line,
    -- Todo: 尚未認領且尚未結束
    groupBitmapStateIf(cityHash64(task_id), snapshot_date < COALESCE(task_claim_date, task_end_date, today() + 1)) AS todo_bm,
    -- Doing: 已認領但尚未結束
    groupBitmapStateIf(
        cityHash64(task_id),
        task_claim_date IS NOT NULL
        AND snapshot_date >= task_claim_date
        AND (task_end_date IS NULL OR snapshot_date < task_end_date)
    ) AS doing_bm,
    -- Done: 已經結束
    groupBitmapStateIf(cityHash64(task_id), task_end_date IS NOT NULL AND snapshot_date >= task_end_date) AS done_bm,
    now() AS _refresh_time
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayDistinct(arrayFilter(
    d -> d IS NOT NULL,
    [task_start_date, task_claim_date, task_end_date]
)) AS snapshot_date
WHERE is_excluded = 0
  AND snapshot_date >= toDate('{start_ts}')
  AND snapshot_date <= toDate('{end_ts}')
GROUP BY snapshot_date, vx_type, region, plant, factory, line;
