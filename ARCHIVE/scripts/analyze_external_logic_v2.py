#!/usr/bin/env python3
"""深入分析外部系統的指標計算邏輯"""

import clickhouse_connect

# 外部 ClickHouse 連線
ext = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

# 本地 ClickHouse 連線
local = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

print('=== 深入分析外部系統的指標計算邏輯 ===')

# 1. 檢查 silver_enriched_taskinst 的 task_state 分布
print('\n1. silver_enriched_taskinst 的 task_state 分布:')
result = ext.query('''
    SELECT task_state, count() AS cnt
    FROM silver_enriched_taskinst
    GROUP BY task_state
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 2. 檢查 silver_enriched_taskinst 的 task_bypass 分布
print('\n2. silver_enriched_taskinst 的 task_bypass 分布:')
result = ext.query('''
    SELECT task_bypass, count() AS cnt
    FROM silver_enriched_taskinst
    GROUP BY task_bypass
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 3. 檢查 silver_enriched_taskinst 的 proc_vx 分布
print('\n3. silver_enriched_taskinst 的 proc_vx 分布:')
result = ext.query('''
    SELECT proc_vx, count() AS cnt
    FROM silver_enriched_taskinst
    GROUP BY proc_vx
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 4. 檢查外部系統是否排除 Bypass 任務
print('\n4. 檢查外部系統是否排除 Bypass 任務:')
print('   silver_enriched_taskinst 的 task_bypass 全部是 N，表示已排除 Bypass 任務')

# 5. 檢查外部系統的 task_def_key 前綴分布
print('\n5. gold_daily_task_metrics 的 task_def_key 前綴分布:')
result = ext.query('''
    SELECT 
        substring(task_def_key, 1, 2) AS prefix,
        sum(todo_count) AS todo,
        sum(doing_count) AS doing,
        sum(done_count) AS done
    FROM gold_daily_task_metrics
    WHERE task_def_key IS NOT NULL
    GROUP BY prefix
    ORDER BY done DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: TODO={row[1]:,}, DOING={row[2]:,}, DONE={row[3]:,}')

# 6. 檢查外部系統是否包含 E/C 開頭的任務
print('\n6. 檢查外部系統是否包含 E/C 開頭的任務:')
result = ext.query('''
    SELECT 
        task_def_key,
        sum(todo_count) AS todo,
        sum(doing_count) AS doing,
        sum(done_count) AS done
    FROM gold_daily_task_metrics
    WHERE task_def_key LIKE 'E%' OR task_def_key LIKE 'C%'
    GROUP BY task_def_key
    ORDER BY done DESC
    LIMIT 10
''')
for row in result.result_rows:
    print(f'   {row[0]}: TODO={row[1]:,}, DOING={row[2]:,}, DONE={row[3]:,}')

# 7. 比較同一天的資料量
print('\n7. 比較 2025-12-28 的資料量:')
# 外部系統
result = ext.query('''
    SELECT 
        sum(todo_count) AS todo,
        sum(doing_count) AS doing,
        sum(done_count) AS done,
        sum(created_count) AS created
    FROM gold_daily_task_metrics
    WHERE snapshot_date = '2025-12-28'
''')
ext_row = result.result_rows[0]
print(f'   外部系統: TODO={ext_row[0]:,}, DOING={ext_row[1]:,}, DONE={ext_row[2]:,}, CREATED={ext_row[3]:,}')

# 本地系統
result = local.query('''
    SELECT 
        countIf(task_status = 'TODO') AS todo,
        countIf(task_status = 'DOING') AS doing,
        countIf(task_status = 'DONE') AS done,
        count() AS total
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE task_create_date = '2025-12-28'
      AND is_excluded = 0
''')
local_row = result.result_rows[0]
print(f'   本地系統: TODO={local_row[0]:,}, DOING={local_row[1]:,}, DONE={local_row[2]:,}, TOTAL={local_row[3]:,}')

# 8. 檢查外部系統的 silver_enriched_taskinst 資料來源
print('\n8. silver_enriched_taskinst 的資料量:')
result = ext.query('SELECT count() FROM silver_enriched_taskinst')
print(f'   筆數: {result.result_rows[0][0]:,}')

# 9. 檢查外部系統的日期範圍
print('\n9. silver_enriched_taskinst 的日期範圍:')
result = ext.query('''
    SELECT 
        min(toDate(start_time)) AS min_date,
        max(toDate(start_time)) AS max_date
    FROM silver_enriched_taskinst
    WHERE start_time IS NOT NULL
''')
row = result.result_rows[0]
print(f'   最早: {row[0]}, 最晚: {row[1]}')

# 10. 檢查外部系統的 Vx 計算邏輯
print('\n10. 檢查外部系統的 Vx 計算邏輯:')
result = ext.query('''
    SELECT 
        proc_vx,
        substring(task_def_key, 1, 2) AS task_prefix,
        count() AS cnt
    FROM silver_enriched_taskinst
    WHERE proc_vx IS NOT NULL
    GROUP BY proc_vx, task_prefix
    ORDER BY cnt DESC
    LIMIT 10
''')
for row in result.result_rows:
    print(f'   proc_vx={row[0]}, task_prefix={row[1]}: {row[2]:,}')
