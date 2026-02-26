import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
r = client.query("SELECT varinst_region, varinst_plant, varinst_factory, varinst_lineName, count() FROM silver.mv_varinst_pivoted GROUP BY varinst_region, varinst_plant, varinst_factory, varinst_lineName ORDER BY count() DESC LIMIT 10")
for row in r.result_rows:
    print(row)
