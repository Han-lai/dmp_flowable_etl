-- Enable experimental feature
SET allow_experimental_refreshable_materialized_view = 1;

-- Drop existing MV
DROP TABLE IF EXISTS gold.rmv_l5_task_completion;

-- Recreate MV with fixed JOIN logic
CREATE MATERIALIZED VIEW gold.rmv_l5_task_completion
REFRESH EVERY 1 HOUR
(
    `snapshot_date` Date,
    `vx_type` String,
    `region` String,
    `plant` String,
    `factory` String,
    `line` String,
    `total_task` UInt64,
    `todo_count` UInt64,
    `doing_count` UInt64,
    `done_count` UInt64,
    `completion_rate` Nullable(Float64),
    `execution_rate` Nullable(Float64),
    `acc_todo_doing` UInt64,
    `_refresh_time` DateTime64(3)
)
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (snapshot_date, vx_type, region, plant, factory, line)
TTL snapshot_date + toIntervalYear(1)
SETTINGS index_granularity = 8192
AS WITH
    daily_base AS
    (
        SELECT
            snapshot_date,
            vx_type,
            region,
            plant,
            factory,
            line,
            count() AS total_task,
            countIf((snapshot_date < toDate(task_claim_date)) OR ((snapshot_date < toDate(task_end_date)) AND (task_claim_date IS NULL))) AS todo_count,
            countIf((snapshot_date >= toDate(task_claim_date)) AND ((snapshot_date < toDate(task_end_date)) OR (task_end_date IS NULL))) AS doing_count,
            countIf((snapshot_date >= toDate(task_end_date)) AND ((task_end_date IS NULL) = 0)) AS done_count
        FROM silver.mv_fact_task_vx FINAL
        ARRAY JOIN arrayDistinct(arrayFilter(d -> (d IS NOT NULL), [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
        WHERE is_excluded = 0
        GROUP BY
            snapshot_date,
            vx_type,
            region,
            plant,
            factory,
            line
    ),
    acc_stats AS
    (
        SELECT
            d.snapshot_date AS snapshot_date,
            t.vx_type AS vx_type,
            t.region AS region,
            t.plant AS plant,
            t.factory AS factory,
            t.line AS line,
            uniqExact(t.task_id) AS acc_todo_doing
        FROM 
        (
            SELECT DISTINCT snapshot_date
            FROM silver.mv_fact_task_vx FINAL
            ARRAY JOIN arrayDistinct(arrayFilter(d -> (d IS NOT NULL), [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
            WHERE is_excluded = 0
        ) AS d
        CROSS JOIN silver.mv_fact_task_vx AS t 
        WHERE t.is_excluded = 0
          AND t.task_start_date <= d.snapshot_date
          AND (t.task_end_date IS NULL OR t.task_end_date > d.snapshot_date)
          AND (t.task_start_date >= subtractDays(d.snapshot_date, 6) OR (t.task_claim_date IS NOT NULL AND t.task_claim_date >= subtractDays(d.snapshot_date, 6)))
        GROUP BY
            snapshot_date,
            vx_type,
            region,
            plant,
            factory,
            line
    )
SELECT
    coalesce(base.snapshot_date, acc.snapshot_date) AS snapshot_date,
    coalesce(base.vx_type, acc.vx_type) AS vx_type,
    coalesce(base.region, acc.region) AS region,
    coalesce(base.plant, acc.plant) AS plant,
    coalesce(base.factory, acc.factory) AS factory,
    coalesce(base.line, acc.line) AS line,
    coalesce(base.total_task, 0) AS total_task,
    coalesce(base.todo_count, 0) AS todo_count,
    coalesce(base.doing_count, 0) AS doing_count,
    coalesce(base.done_count, 0) AS done_count,
    round((coalesce(base.done_count, 0) * 100.) / nullIf(coalesce(base.total_task, 0), 0), 2) AS completion_rate,
    round(((coalesce(base.doing_count, 0) + coalesce(base.done_count, 0)) * 100.) / nullIf(coalesce(base.total_task, 0), 0), 2) AS execution_rate,
    coalesce(acc.acc_todo_doing, 0) AS acc_todo_doing,
    now64(3) AS _refresh_time
FROM daily_base AS base
FULL OUTER JOIN acc_stats AS acc USING (snapshot_date, vx_type, region, plant, factory, line);
