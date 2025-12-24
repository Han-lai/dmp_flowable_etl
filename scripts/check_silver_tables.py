import clickhouse_connect

client = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

print("=== silver database 中的表/View ===")
result = client.query("""
SELECT name, engine 
FROM system.tables 
WHERE database = 'silver' 
ORDER BY engine, name
""")
for row in result.result_rows:
    print(f"  {row[0]:<35} ({row[1]})")
