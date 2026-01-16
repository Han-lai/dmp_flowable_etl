#!/usr/bin/env python3
"""測試 JDBC Bridge 連線"""

import clickhouse_connect

c = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)
print('ClickHouse 連線成功')

# 測試 JDBC Bridge 連線
try:
    result = c.query("SELECT * FROM jdbc('mssql_master', 'SELECT 1 as test')")
    print(f'JDBC Bridge 連線成功: {result.result_rows}')
except Exception as e:
    print(f'JDBC Bridge 連線失敗: {e}')

# 測試查詢 MSSQL 資料庫列表
try:
    result = c.query("SELECT * FROM jdbc('mssql_master', 'SELECT name FROM sys.databases')")
    print(f'MSSQL 資料庫列表:')
    for row in result.result_rows:
        print(f'  - {row[0]}')
except Exception as e:
    print(f'查詢資料庫列表失敗: {e}')
