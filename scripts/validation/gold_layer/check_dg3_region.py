import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
r = client.query("SELECT DISTINCT region, plant, factory, line FROM gold.rmv_l5_task_completion_v2 WHERE plant='DG3'")
print(r.result_rows)
