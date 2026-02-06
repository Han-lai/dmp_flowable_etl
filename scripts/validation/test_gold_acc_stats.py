import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

q = """
WITH
    dates AS
    (
        SELECT DISTINCT snapshot_date
        FROM silver.mv_fact_task_vx
        FINAL
        ARRAY JOIN arrayDistinct(arrayFilter(d -> (d IS NOT NULL), [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
        WHERE is_excluded = 0 AND snapshot_date = '2025-12-25'
    ),
    acc_stats AS
    (
        SELECT
            dates.snapshot_date,
            tasks.vx_type,
            tasks.region,
            tasks.plant,
            tasks.factory,
            tasks.line,
            uniqExact(tasks.task_id) AS acc_todo_doing
        FROM dates
        INNER JOIN silver.mv_fact_task_vx AS tasks ON (tasks.task_start_date <= dates.snapshot_date) 
            AND ((tasks.task_end_date IS NULL) OR (tasks.task_end_date > dates.snapshot_date)) 
            AND ((tasks.task_start_date >= subtractDays(dates.snapshot_date, 6)) 
                 OR ((tasks.task_claim_date IS NOT NULL) AND (tasks.task_claim_date >= subtractDays(dates.snapshot_date, 6))))
        WHERE tasks.is_excluded = 0
        GROUP BY
            dates.snapshot_date,
            tasks.vx_type,
            tasks.region,
            tasks.plant,
            tasks.factory,
            tasks.line
    )
SELECT count() FROM acc_stats
"""

try:
    res = client.query(q)
    print(f"Result: {res.result_rows}")
except Exception as e:
    print(f"Error: {e}")
