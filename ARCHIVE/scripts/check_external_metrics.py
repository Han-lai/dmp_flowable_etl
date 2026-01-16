#!/usr/bin/env python3
"""檢查外部 ClickHouse 的 L5 指標"""

import clickhouse_connect

# 外部 ClickHouse 連線
c = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

print('=== 外部 ClickHouse: flowable_analytics.gold_daily_task_metrics ===')

# 1. 表結構
print('\n1. 表結構:')
result = c.query("DESCRIBE TABLE gold_daily_task_metrics")
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]}')

# 2. 日期範圍
print('\n2. 日期範圍:')
result = c.query('''
    SELECT 
        min(snapshot_date) AS min_date,
        max(snapshot_date) AS max_date,
        count() AS total
    FROM gold_daily_task_metrics
''')
row = result.result_rows[0]
print(f'   最早: {row[0]}, 最晚: {row[1]}, 總筆數: {row[2]:,}')

# 3. 2026-01-15 的資料
print('\n3. 2026-01-15 的資料:')
result = c.query('''
    SELECT count() 
    FROM gold_daily_task_metrics
    WHERE snapshot_date = '2026-01-15'
''')
print(f'   筆數: {result.result_rows[0][0]:,}')

# 4. 2026-01-15 的 Vx 分布
print('\n4. 2026-01-15 的 Vx 分布:')
result = c.query('''
    SELECT 
        proc_vx,
        sum(todo_count) AS todo,
        sum(doing_count) AS doing,
        sum(done_count) AS done,
        sum(terminated_count) AS terminated,
        sum(created_count) AS created
    FROM gold_daily_task_metrics
    WHERE snapshot_date = '2026-01-15'
    GROUP BY proc_vx
    ORDER BY proc_vx
''')
for row in result.result_rows:
    print(f'   {row[0]}: TODO={row[1]:,}, DOING={row[2]:,}, DONE={row[3]:,}, TERMINATED={row[4]:,}, CREATED={row[5]:,}')

# 5. 樣本資料
print('\n5. 樣本資料 (2026-01-15, 前 5 筆):')
result = c.query('''
    SELECT *
    FROM gold_daily_task_metrics
    WHERE snapshot_date = '2026-01-15'
    LIMIT 5
''')
print(f'   欄位: {result.column_names}')
for row in result.result_rows:
    print(f'   {row}')
