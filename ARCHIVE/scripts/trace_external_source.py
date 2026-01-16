#!/usr/bin/env python3
"""追蹤外部系統的資料源頭和邏輯"""

import clickhouse_connect

ext = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

print('=== 追蹤外部系統的資料源頭和邏輯 ===')

# 1. 檢查 silver_enriched_procinst 的建立邏輯（proc_vx 來源）
print('\n1. silver_enriched_procinst 的建立邏輯:')
try:
    result = ext.query("SHOW CREATE TABLE silver_enriched_procinst")
    print(result.result_rows[0][0])
except Exception as e:
    print(f'   錯誤: {e}')

# 2. 檢查 silver_proc_variables_pivoted 的建立邏輯
print('\n' + '='*80)
print('2. silver_proc_variables_pivoted 的建立邏輯:')
try:
    result = ext.query("SHOW CREATE TABLE silver_proc_variables_pivoted")
    print(result.result_rows[0][0])
except Exception as e:
    print(f'   錯誤: {e}')

# 3. 檢查 silver_task_variables_pivoted 的建立邏輯
print('\n' + '='*80)
print('3. silver_task_variables_pivoted 的建立邏輯:')
try:
    result = ext.query("SHOW CREATE TABLE silver_task_variables_pivoted")
    print(result.result_rows[0][0])
except Exception as e:
    print(f'   錯誤: {e}')

# 4. 檢查 gold_daily_task_metrics_rmv 的建立邏輯
print('\n' + '='*80)
print('4. gold_daily_task_metrics_rmv 的建立邏輯:')
try:
    result = ext.query("SHOW CREATE TABLE gold_daily_task_metrics_rmv")
    print(result.result_rows[0][0])
except Exception as e:
    print(f'   錯誤: {e}')
