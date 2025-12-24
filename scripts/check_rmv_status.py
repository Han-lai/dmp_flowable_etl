import clickhouse_connect
client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

print('=== RMV 刷新狀態 ===')
result = client.query('''
SELECT 
    database,
    view,
    status,
    last_refresh_time,
    next_refresh_time
FROM system.view_refreshes
WHERE database = 'silver'
ORDER BY view
''')

print(f"{'View':<35} | {'Status':<10} | {'Last Refresh':<25} | Next Refresh")
print('-' * 100)
for row in result.result_rows:
    print(f'{row[1]:<35} | {row[2]:<10} | {str(row[3]):<25} | {row[4]}')
