#!/usr/bin/env python3
"""比較本地和外部系統的 2025-12-28 結果"""

import clickhouse_connect

local = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

ext = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

print('=== 比較 2025-12-28 的結果 ===')

# 1. 本地系統
print('\n1. 本地系統 (gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT):')
result = local.query('''
    SELECT 
        vx_type,
        sum(todo_qty) AS todo,
        sum(doing_qty) AS doing,
        sum(done_qty) AS done,
        sum(total_task_qty) AS total
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
    GROUP BY vx_type
    ORDER BY vx_type
''')
local_total = {'todo': 0, 'doing': 0, 'done': 0, 'total': 0}
for row in result.result_rows:
    print(f'   {row[0]}: TODO={row[1]:,}, DOING={row[2]:,}, DONE={row[3]:,}, TOTAL={row[4]:,}')
    local_total['todo'] += row[1]
    local_total['doing'] += row[2]
    local_total['done'] += row[3]
    local_total['total'] += row[4]
print(f'   總計: TODO={local_total["todo"]:,}, DOING={local_total["doing"]:,}, DONE={local_total["done"]:,}, TOTAL={local_total["total"]:,}')

# 2. 外部系統
print('\n2. 外部系統 (gold_daily_task_metrics):')
result = ext.query('''
    SELECT 
        sum(todo_count) AS todo,
        sum(doing_count) AS doing,
        sum(done_count) AS done,
        sum(created_count) AS created
    FROM gold_daily_task_metrics
    WHERE snapshot_date = '2025-12-28'
''')
row = result.result_rows[0]
print(f'   總計: TODO={row[0]:,}, DOING={row[1]:,}, DONE={row[2]:,}, CREATED={row[3]:,}')

# 3. 差異分析
print('\n3. 差異分析:')
print(f'   本地 TODO: {local_total["todo"]:,}, 外部 TODO: {row[0]:,}, 差異: {local_total["todo"] - row[0]:,}')
print(f'   本地 DOING: {local_total["doing"]:,}, 外部 DOING: {row[1]:,}, 差異: {local_total["doing"] - row[1]:,}')
print(f'   本地 DONE: {local_total["done"]:,}, 外部 DONE: {row[2]:,}, 差異: {local_total["done"] - row[2]:,}')
print(f'   本地 TOTAL: {local_total["total"]:,}, 外部 CREATED: {row[3]:,}, 差異: {local_total["total"] - row[3]:,}')
