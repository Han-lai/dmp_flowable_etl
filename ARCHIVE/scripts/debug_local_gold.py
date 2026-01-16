#!/usr/bin/env python3
"""Debug 本地系統的 Gold 快照問題"""

import clickhouse_connect

local = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

print('=== Debug 本地系統的 Gold 快照問題 ===')

# 1. 檢查 Silver 層資料
print('\n1. Silver 層資料:')
result = local.query('SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION')
print(f'   FACT_TASK_VX_ATTRIBUTION: {result.result_rows[0][0]:,} 筆')

# 2. 檢查 task_status 分布
print('\n2. task_status 分布:')
result = local.query('''
    SELECT task_status, count() AS cnt
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    GROUP BY task_status
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 3. 檢查 is_excluded 分布
print('\n3. is_excluded 分布:')
result = local.query('''
    SELECT is_excluded, count() AS cnt
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    GROUP BY is_excluded
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 4. 檢查 vx_type 分布
print('\n4. vx_type 分布:')
result = local.query('''
    SELECT vx_type, count() AS cnt
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    GROUP BY vx_type
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 5. 檢查 task_create_date 範圍
print('\n5. task_create_date 範圍:')
result = local.query('''
    SELECT 
        min(task_create_date) AS min_date,
        max(task_create_date) AS max_date
    FROM silver.FACT_TASK_VX_ATTRIBUTION
''')
row = result.result_rows[0]
print(f'   最早: {row[0]}, 最晚: {row[1]}')

# 6. 檢查 Gold 快照的 SQL 邏輯
print('\n6. Gold 快照的 SQL 邏輯問題:')
print('   Gold 快照使用 task_create_date = snapshot_date')
print('   但今天是 2026-01-15，資料最晚只到 2026-01-02')
print('   所以 2026-01-15 的快照會是 0 筆')

# 7. 檢查 2025-12-28 的資料
print('\n7. 檢查 2025-12-28 的資料:')
result = local.query('''
    SELECT 
        vx_type,
        countIf(task_status = 'TODO') AS todo,
        countIf(task_status = 'DOING') AS doing,
        countIf(task_status = 'DONE') AS done,
        count() AS total
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = '2025-12-28'
      AND is_excluded = 0
    GROUP BY vx_type
    ORDER BY vx_type
''')
for row in result.result_rows:
    print(f'   {row[0]}: TODO={row[1]:,}, DOING={row[2]:,}, DONE={row[3]:,}, TOTAL={row[4]:,}')

# 8. 檢查外部系統 2025-12-28 的資料
print('\n8. 外部系統 2025-12-28 的資料:')
ext = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)
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
print(f'   TODO={row[0]:,}, DOING={row[1]:,}, DONE={row[2]:,}, CREATED={row[3]:,}')

# 9. 關鍵差異分析
print('\n9. 關鍵差異分析:')
print('   外部系統: 使用 toDate(start_time) = snapshot_date')
print('   本地系統: 使用 task_create_date = snapshot_date')
print('   這兩個應該是一樣的，但需要確認 task_create_date 的來源')

# 10. 檢查 Bronze 層的 TaskCreateDate
print('\n10. 檢查 Bronze 層的 TaskCreateDate:')
result = local.query('''
    SELECT 
        min(TaskCreateDate) AS min_date,
        max(TaskCreateDate) AS max_date,
        count() AS total
    FROM bronze.common_flowable_task_stats
''')
row = result.result_rows[0]
print(f'   最早: {row[0]}, 最晚: {row[1]}, 總數: {row[2]:,}')
