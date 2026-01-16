#!/usr/bin/env python3
"""檢查任務日期範圍"""

import clickhouse_connect

c = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

print('=== 任務日期範圍 ===')
result = c.query('''
    SELECT 
        min(task_create_date) AS min_date,
        max(task_create_date) AS max_date,
        count() AS total
    FROM silver.FACT_TASK_VX_ATTRIBUTION
''')
row = result.result_rows[0]
print(f'最早日期: {row[0]}')
print(f'最晚日期: {row[1]}')
print(f'總筆數: {row[2]:,}')

print('\n=== 最近 7 天的任務數 ===')
result = c.query('''
    SELECT 
        task_create_date,
        count() AS cnt
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    GROUP BY task_create_date
    ORDER BY task_create_date DESC
    LIMIT 10
''')
for row in result.result_rows:
    print(f'  {row[0]}: {row[1]:,}')

print('\n=== 今天 (2026-01-15) 的任務 ===')
result = c.query('''
    SELECT count() 
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = toDate('2026-01-15')
''')
print(f'今天任務數: {result.result_rows[0][0]:,}')
