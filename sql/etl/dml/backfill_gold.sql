-- Sync unified gold table from milestone and acc tables
-- This creates a physical table with the same structure as the old version

INSERT INTO gold.rmv_l5_task_completion_phys
SELECT
    COALESCE(m.snapshot_date, a.snapshot_date) AS snapshot_date,
    COALESCE(m.vx_type, a.vx_type) AS vx_type,
    COALESCE(m.region, a.region) AS region,
    COALESCE(m.plant, a.plant) AS plant,
    COALESCE(m.factory, a.factory) AS factory,
    COALESCE(m.line, a.line) AS line,
    COALESCE(m.total_task, 0) AS total_task,
    COALESCE(m.todo_count, 0) AS todo_count,
    COALESCE(m.doing_count, 0) AS doing_count,
    COALESCE(m.done_count, 0) AS done_count,
    COALESCE(a.acc_todo_doing, 0) AS acc_todo_doing,
    now() AS _refresh_time
FROM (
    SELECT * FROM gold.rmv_l5_milestone_phys FINAL
    WHERE snapshot_date >= toDate('{start_ts}')
      AND snapshot_date <= toDate('{end_ts}')
) m
FULL OUTER JOIN (
    SELECT * FROM gold.rmv_l5_acc_phys FINAL
    WHERE snapshot_date >= toDate('{start_ts}')
      AND snapshot_date <= toDate('{end_ts}')
) a
    ON m.snapshot_date = a.snapshot_date
   AND m.vx_type = a.vx_type
   AND m.region = a.region
   AND m.plant = a.plant
   AND m.factory = a.factory
   AND m.line = a.line;
