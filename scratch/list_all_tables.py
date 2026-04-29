import clickhouse_connect

ch = clickhouse_connect.get_client(host='10.146.206.76', port=8123, username='default', password='1qaz2wsx3edc', database='default')

print('--- All Tables in bronze, silver, gold ---')
q = "SELECT database, name FROM system.tables WHERE database IN ('bronze', 'silver', 'gold')"
for row in ch.query(q).result_rows:
    print(row)
