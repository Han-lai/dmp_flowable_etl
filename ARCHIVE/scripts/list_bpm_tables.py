#!/usr/bin/env python3
"""列出 APP_SRV_BPM 資料庫中的表"""

import clickhouse_connect

c = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

print('=== APP_SRV_BPM 資料庫中的表 ===')
try:
    result = c.query("""
        SELECT * FROM jdbc('mssql_master', '
            SELECT TABLE_NAME 
            FROM APP_SRV_BPM.INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = ''BASE TABLE''
            AND TABLE_NAME LIKE ''ACT_%''
            ORDER BY TABLE_NAME
        ')
    """)
    for row in result.result_rows:
        print(f'  - {row[0]}')
except Exception as e:
    print(f'查詢失敗: {e}')
