"""檢查我的環境使用的技術"""
import clickhouse_connect

my_env = clickhouse_connect.get_client(
    host='10.136.218.207', port=8121, 
    username='default', password='default'
)

print('=== 檢查我的環境 (port 8121) ===\n')

# 1. 檢查 databases
print('1. Databases:')
result = my_env.query("SELECT name FROM system.databases WHERE name NOT IN ('system', 'INFORMATION_SCHEMA', 'information_schema') ORDER BY name")
for row in result.result_rows:
    print(f'   - {row[0]}')

# 2. 檢查表格 engine 類型
print('\n2. 表格 engine 類型:')
result = my_env.query("""
    SELECT database, engine, count(*) as cnt 
    FROM system.tables 
    WHERE database NOT IN ('system', 'INFORMATION_SCHEMA', 'information_schema')
    GROUP BY database, engine
    ORDER BY database, cnt DESC
""")
for row in result.result_rows:
    print(f'   {row[0]}.{row[1]}: {row[2]} 張')

# 3. 檢查 jdbc 函數
print('\n3. JDBC Bridge 檢查:')
result = my_env.query("SELECT name FROM system.table_functions WHERE name LIKE '%jdbc%'")
if result.result_rows:
    print('   ✅ jdbc table function 存在')
else:
    print('   ❌ jdbc table function 不存在')

# 4. 檢查是否有 JDBC engine 表格
print('\n4. JDBC/ODBC engine 表格:')
result = my_env.query("""
    SELECT database, name, engine 
    FROM system.tables 
    WHERE engine LIKE '%JDBC%' OR engine LIKE '%ODBC%'
""")
if result.result_rows:
    for row in result.result_rows:
        print(f'   - {row[0]}.{row[1]}: {row[2]}')
else:
    print('   無 JDBC/ODBC engine 表格')

# 5. 檢查 bronze 層表格
print('\n5. Bronze 層表格:')
result = my_env.query("""
    SELECT name, engine 
    FROM system.tables 
    WHERE database = 'bronze'
    ORDER BY name
""")
for row in result.result_rows:
    print(f'   - {row[0]} ({row[1]})')

# 6. 檢查 silver 層表格
print('\n6. Silver 層表格:')
result = my_env.query("""
    SELECT name, engine 
    FROM system.tables 
    WHERE database = 'silver'
    ORDER BY name
""")
for row in result.result_rows:
    print(f'   - {row[0]} ({row[1]})')

# 7. 檢查是否有 _airbyte 欄位
print('\n7. Airbyte 同步痕跡:')
result = my_env.query("""
    SELECT DISTINCT table
    FROM system.columns 
    WHERE database = 'bronze' AND name LIKE '_airbyte%'
""")
if result.result_rows:
    print(f'   有 {len(result.result_rows)} 張表有 _airbyte 欄位')
else:
    print('   無 _airbyte 欄位 (未使用 Airbyte)')

# 8. 檢查 RMV 刷新狀態
print('\n8. RMV 刷新狀態:')
result = my_env.query("""
    SELECT view, status, last_refresh_time
    FROM system.view_refreshes
    WHERE database = 'silver'
    ORDER BY view
""")
for row in result.result_rows:
    print(f'   - {row[0]}: {row[1]} (last: {row[2]})')

print('\n=== 結論 ===')
print('我的環境使用:')
print('- Bronze 層: ReplacingMergeTree (透過 JDBC Bridge 從 MSSQL 同步)')
print('- Silver 層: View + Refreshable Materialized View (RMV)')
