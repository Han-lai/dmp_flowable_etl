import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
r = client.query("SELECT * FROM silver.mv_dim_mfg_five_level WHERE line_name='ST02'")
for row in r.result_rows:
    print(row)
