import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
r = client.query("SELECT count() FROM silver.mv_fact_task_vx")
print("Row count in silver.mv_fact_task_vx:", r.result_rows[0][0])

r2 = client.query("SELECT count() FROM silver.mv_varinst_pivoted")
print("Row count in silver.mv_varinst_pivoted:", r2.result_rows[0][0])
