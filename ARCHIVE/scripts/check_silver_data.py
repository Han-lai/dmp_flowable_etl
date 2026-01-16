#!/usr/bin/env python3
"""檢查 Silver 層資料"""

import clickhouse_connect

c = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

# 檢查表結構
print('=== FACT_TASK_VX_ATTRIBUTION 欄位 ===')
result = c.query("SELECT name, type FROM system.columns WHERE database = 'silver' AND table = 'FACT_TASK_VX_ATTRIBUTION'")
for row in result.result_rows:
    print(f'  {row[0]}: {row[1]}')

# 檢查資料
print('\n=== 資料樣本 ===')
result = c.query('SELECT * FROM silver.FACT_TASK_VX_ATTRIBUTION LIMIT 3')
print(f'欄位: {result.column_names}')
for row in result.result_rows:
    print(f'  {row}')
