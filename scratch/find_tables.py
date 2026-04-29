import clickhouse_connect

ch = clickhouse_connect.get_client(host='10.146.206.76', port=8123, username='default', password='1qaz2wsx3edc', database='default')

print('--- Searching for TaskStats related tables ---')
q = "SELECT database, name FROM system.tables WHERE name ILIKE '%task_stats%' OR name ILIKE '%FlowableTaskStats%'"
for row in ch.query(q).result_rows:
    print(row)

print('\n--- Searching for BPM raw tables ---')
q2 = "SELECT database, name FROM system.tables WHERE name ILIKE '%taskinst%'"
for row in ch.query(q2).result_rows:
    print(row)
