#!/usr/bin/env python3
"""Debug Gold 快照的計數問題"""

import clickhouse_connect

local = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

print('=== Debug Gold 快照的計數問題 ===')

# 1. Silver 層 is_excluded = 0 的數量
print('\n1. Silver 層 is_excluded = 0 的數量 (2025-12-28):')
result = local.query('''
    SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = '2025-12-28'
      AND is_excluded = 0
''')
print(f'   數量: {result.result_rows[0][0]:,}')

# 2. 檢查 is_excluded = 0 的 state_on_date 分布
print('\n2. is_excluded = 0 的 state_on_date 分布:')
result = local.query('''
    SELECT 
        multiIf(
            task_end_time IS NOT NULL AND toDate(task_end_time) <= toDate('2025-12-28'), 'DONE',
            task_claim_time IS NOT NULL AND toDate(task_claim_time) <= toDate('2025-12-28'), 'DOING',
            'TODO'
        ) AS state_on_date,
        count() AS cnt
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = '2025-12-28'
      AND is_excluded = 0
    GROUP BY state_on_date
    ORDER BY cnt DESC
''')
total = 0
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')
    total += row[1]
print(f'   總計: {total:,}')

# 3. 檢查 Gold 快照的數量
print('\n3. Gold 快照的數量 (2025-12-28):')
result = local.query('''
    SELECT 
        sum(todo_qty) AS todo,
        sum(doing_qty) AS doing,
        sum(done_qty) AS done,
        sum(total_task_qty) AS total
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
''')
row = result.result_rows[0]
print(f'   TODO={row[0]:,}, DOING={row[1]:,}, DONE={row[2]:,}, TOTAL={row[3]:,}')

# 4. 檢查 vx_type 分布
print('\n4. Silver 層 vx_type 分布 (is_excluded = 0):')
result = local.query('''
    SELECT vx_type, count() AS cnt
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = '2025-12-28'
      AND is_excluded = 0
    GROUP BY vx_type
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 5. 檢查 V1 的 is_excluded 分布
print('\n5. V1 的 is_excluded 分布:')
result = local.query('''
    SELECT is_excluded, exclude_reason, count() AS cnt
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = '2025-12-28'
      AND vx_type = 'V1'
    GROUP BY is_excluded, exclude_reason
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   is_excluded={row[0]}, reason={row[1]}: {row[2]:,}')
