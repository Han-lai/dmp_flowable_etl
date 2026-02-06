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
            d.snapshot_date AS snapshot_date,
            t.vx_type AS vx_type,
            t.region AS region,
            t.plant AS plant,
            t.factory AS factory,
            t.line AS line,
            uniqExact(t.task_id) AS acc_todo_doing
        FROM dates AS d
        CROSS JOIN silver.mv_fact_task_vx AS t 
        WHERE t.is_excluded = 0
          AND t.task_start_date <= d.snapshot_date
          AND (t.task_end_date IS NULL OR t.task_end_date > d.snapshot_date)
          AND (t.task_start_date >= subtractDays(d.snapshot_date, 6) OR (t.task_claim_date IS NOT NULL AND t.task_claim_date >= subtractDays(d.snapshot_date, 6)))
        GROUP BY snapshot_date, vx_type, region, plant, factory, line
    )
SELECT count() FROM acc_stats
"""

try:
    res = client.query(q)
    print(f"Result: {res.result_rows}")
except Exception as e:
    print(f"Error: {e}")
