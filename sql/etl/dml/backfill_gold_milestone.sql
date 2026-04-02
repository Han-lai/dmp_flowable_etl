-- Phase 4a: Gold Layer Milestone Aggregation (Todo/Doing/Done)
-- Variables: {start_ts}, {end_ts}
-- Target: gold.rmv_l5_milestone_phys

INSERT INTO gold.rmv_l5_milestone_phys
SELECT
    snapshot_date,
    vx_type, region, plant, factory, line,
    count()                                                                            AS total_task,
    countIf(snapshot_date < COALESCE(task_claim_date, task_end_date, today() + 1))    AS todo_count,
    countIf(
        task_claim_date IS NOT NULL
        AND snapshot_date >= task_claim_date
        AND (task_end_date IS NULL OR snapshot_date < task_end_date)
    )                                                                                  AS doing_count,
    countIf(task_end_date IS NOT NULL AND snapshot_date >= task_end_date)              AS done_count,
    now() AS _refresh_time
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayDistinct(arrayFilter(
    d -> d IS NOT NULL,
    [task_start_date, task_claim_date, task_end_date]
)) AS snapshot_date
WHERE is_excluded = 0
  AND snapshot_date >= toDate('{start_ts}')
  AND snapshot_date <= toDate('{end_ts}')
  AND task_start_date <= toDate('{end_ts}')
GROUP BY snapshot_date, vx_type, region, plant, factory, line
