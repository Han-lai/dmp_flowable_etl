#!/usr/bin/env python3
"""Debug FlowableTaskStats 同步問題"""

import clickhouse_connect

c = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

# 測試直接查詢
print('=== 測試 JDBC 查詢 ===')

# 測試 1: 查詢前 10 筆
print('\n1. 查詢前 10 筆:')
result = c.query("SELECT * FROM jdbc('mssql_master', 'SELECT TOP 10 * FROM APP_SRV_COMMON.dbo.FlowableTaskStats')")
print(f'   取得 {len(result.result_rows)} 筆')

# 測試 2: 查詢總數
print('\n2. 查詢總數:')
result = c.query("SELECT count() FROM jdbc('mssql_master', 'SELECT 1 FROM APP_SRV_COMMON.dbo.FlowableTaskStats')")
print(f'   總數: {result.result_rows[0][0]:,}')

# 測試 3: 查詢欄位
print('\n3. 查詢欄位:')
result = c.query("""
    SELECT * FROM jdbc('mssql_master', '
        SELECT COLUMN_NAME, DATA_TYPE 
        FROM APP_SRV_COMMON.INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = ''FlowableTaskStats''
    ')
""")
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]}')

# 測試 4: 不用 SELECT * 試試
print('\n4. 測試指定欄位查詢:')
result = c.query("""
    SELECT * FROM jdbc('mssql_master', '
        SELECT TOP 5 TaskDefinitionKey, TaskStatus, LastUpdatedTime 
        FROM APP_SRV_COMMON.dbo.FlowableTaskStats
    ')
""")
print(f'   取得 {len(result.result_rows)} 筆')
for row in result.result_rows:
    print(f'   {row}')
