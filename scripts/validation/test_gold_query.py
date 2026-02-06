import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

q = """
WITH
    daily_base AS
    (
        SELECT
            snapshot_date,
            vx_type,
            region,
            plant,
            factory,
            line,
            count() AS total_task
        FROM silver.mv_fact_task_vx
        FINAL
        ARRAY JOIN arrayDistinct(arrayFilter(d -> (d IS NOT NULL), [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
        WHERE is_excluded = 0 AND snapshot_date = '2025-12-25'
        GROUP BY snapshot_date, vx_type, region, plant, factory, line
    )
SELECT count() FROM daily_base
"""

try:
    res = client.query(q)
    print(f"Result: {res.result_rows}")
except Exception as e:
    print(f"Error: {e}")
