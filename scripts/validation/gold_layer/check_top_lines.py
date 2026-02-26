import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
r = client.query("SELECT region, plant, factory, line, count() FROM silver.mv_fact_task_vx GROUP BY region, plant, factory, line ORDER BY count() DESC LIMIT 10")
for row in r.result_rows:
    print(row)
