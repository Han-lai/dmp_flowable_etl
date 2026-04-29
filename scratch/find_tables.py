import clickhouse_connect

ch = clickhouse_connect.get_client(host='REDACTED_IP', port=8123, username='default', password='REDACTED_PASSWORD', database='default')

print('--- Searching for TaskStats related tables ---')
q = "SELECT database, name FROM system.tables WHERE name ILIKE '%task_stats%' OR name ILIKE '%FlowableTaskStats%'"
for row in ch.query(q).result_rows:
    print(row)

print('\n--- Searching for BPM raw tables ---')
q2 = "SELECT database, name FROM system.tables WHERE name ILIKE '%taskinst%'"
for row in ch.query(q2).result_rows:
    print(row)
