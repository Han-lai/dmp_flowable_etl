import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
r = client.query("SELECT region, plant, factory, line, count() FROM silver.mv_fact_task_vx WHERE line='ST02' GROUP BY region, plant, factory, line")
for row in r.result_rows:
    print(row)
