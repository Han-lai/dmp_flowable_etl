-- Phase 4: Gold Layer Aggregation (Time-Bounded)
-- Variables: {start_date}, {end_date}
-- Target: gold.rmv_l5_task_completion_phys (Physical SummingMergeTree)

INSERT INTO gold.rmv_l5_task_completion_phys
WITH 
daily_base AS (
    SELECT
        snapshot_date,
        vx_type,
        region, plant, factory, line,
        count() AS total_task,
        countIf(snapshot_date < toDate(task_claim_date) OR (snapshot_date < toDate(task_end_date) AND task_claim_date IS NULL)) AS todo_count,
        countIf(snapshot_date >= toDate(task_claim_date) AND (snapshot_date < toDate(task_end_date) OR task_end_date IS NULL)) AS doing_count,
        countIf(snapshot_date >= toDate(task_end_date) AND task_end_date IS NULL = 0) AS done_count
    FROM silver.mv_fact_task_vx FINAL
    ARRAY JOIN arrayDistinct(arrayFilter(d -> d IS NOT NULL, [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
    WHERE is_excluded = 0
      AND snapshot_date >= toDate('{start_date}') AND snapshot_date <= toDate('{end_date}')
    GROUP BY snapshot_date, vx_type, region, plant, factory, line
),
acc_stats AS (
    SELECT
        snapshot_date,
        vx_type,
        region, plant, factory, line,
        uniqExact(task_id) AS acc_todo_doing
    FROM (
        SELECT
            task_id,
            vx_type,
            region, plant, factory, line,
            arrayMap(d -> toDate(d), 
                range(
                    toUInt32(task_start_date), 
                    toUInt32(least(
                        COALESCE(task_end_date, today() + 2), 
                        greatest(task_start_date, COALESCE(task_claim_date, task_start_date)) + 7
                    ))
                )
            ) AS dates
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0
    )
    ARRAY JOIN dates AS snapshot_date
    WHERE snapshot_date >= toDate('{start_date}') AND snapshot_date <= toDate('{end_date}')
    GROUP BY snapshot_date, vx_type, region, plant, factory, line
)
SELECT
    COALESCE(base.snapshot_date, acc.snapshot_date) AS snapshot_date,
    COALESCE(base.vx_type, acc.vx_type) AS vx_type,
    COALESCE(base.region, acc.region) AS region,
    COALESCE(base.plant, acc.plant) AS plant,
    COALESCE(base.factory, acc.factory) AS factory,
    COALESCE(base.line, acc.line) AS line,
    COALESCE(base.total_task, 0) AS total_task,
    COALESCE(base.todo_count, 0) AS todo_count,
    COALESCE(base.doing_count, 0) AS doing_count,
    COALESCE(base.done_count, 0) AS done_count,
    COALESCE(acc.acc_todo_doing, 0) AS acc_todo_doing,
    now() AS _refresh_time
FROM daily_base AS base
FULL OUTER JOIN acc_stats AS acc USING (snapshot_date, vx_type, region, plant, factory, line)
