import clickhouse_connect

ch = clickhouse_connect.get_client(host='REDACTED_IP', port=8123, username='default', password='REDACTED_PASSWORD', database='default')

print('--- All Tables in bronze, silver, gold ---')
q = "SELECT database, name FROM system.tables WHERE database IN ('bronze', 'silver', 'gold')"
for row in ch.query(q).result_rows:
    print(row)
