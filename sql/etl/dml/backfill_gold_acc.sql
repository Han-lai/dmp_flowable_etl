-- Phase 4b: Gold Layer ACC Aggregation (7-Day Rolling)
-- Variables: {start_ts}, {end_ts}
-- Target: gold.rmv_l5_acc_phys

INSERT INTO gold.rmv_l5_acc_phys
SELECT
    active_date AS snapshot_date,
    vx_type, region, plant, factory, line,
    uniqExact(task_id) AS acc_todo_doing,
    now() AS _refresh_time
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayMap(
    d -> toDate(d),
    range(
        toUInt32(task_start_date),
        toUInt32(least(
            COALESCE(task_end_date, today() + 2),
            task_start_date + 7,
            toDate('{end_ts}') + 1
        ))
    )
) AS active_date
WHERE is_excluded = 0
  AND active_date >= toDate('{start_ts}')
  AND active_date <= toDate('{end_ts}')
  AND task_start_date <= toDate('{end_ts}')
  AND (task_end_date IS NULL OR task_end_date > active_date)
GROUP BY active_date, vx_type, region, plant, factory, line
