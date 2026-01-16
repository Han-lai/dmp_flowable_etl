#!/usr/bin/env python3
"""分析外部系統的指標計算邏輯"""

import clickhouse_connect

# 外部 ClickHouse 連線
ext = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

print('=== 分析外部系統的指標計算邏輯 ===')

# 1. 檢查 silver_enriched_taskinst 表結構（可能是來源表）
print('\n1. silver_enriched_taskinst 表結構:')
try:
    result = ext.query("DESCRIBE TABLE silver_enriched_taskinst")
    for row in result.result_rows:
        print(f'   {row[0]}: {row[1]}')
except Exception as e:
    print(f'   錯誤: {e}')

# 2. 檢查 silver_enriched_taskinst 的資料樣本
print('\n2. silver_enriched_taskinst 資料樣本:')
try:
    result = ext.query("SELECT * FROM silver_enriched_taskinst LIMIT 3")
    print(f'   欄位: {result.column_names}')
    for row in result.result_rows:
        print(f'   {row}')
except Exception as e:
    print(f'   錯誤: {e}')

# 3. 檢查 gold_daily_task_metrics_rmv 表（可能是物化視圖的來源）
print('\n3. gold_daily_task_metrics_rmv 表結構:')
try:
    result = ext.query("DESCRIBE TABLE gold_daily_task_metrics_rmv")
    for row in result.result_rows:
        print(f'   {row[0]}: {row[1]}')
except Exception as e:
    print(f'   錯誤: {e}')

# 4. 檢查是否有物化視圖定義
print('\n4. 檢查物化視圖定義:')
try:
    result = ext.query("SHOW CREATE TABLE gold_daily_task_metrics")
    print(f'   {result.result_rows[0][0]}')
except Exception as e:
    print(f'   錯誤: {e}')

# 5. 檢查 FlowableTaskStats 表結構
print('\n5. FlowableTaskStats 表結構:')
try:
    result = ext.query("DESCRIBE TABLE FlowableTaskStats")
    for row in result.result_rows[:20]:  # 只顯示前 20 個欄位
        print(f'   {row[0]}: {row[1]}')
except Exception as e:
    print(f'   錯誤: {e}')

# 6. 檢查外部系統的 FlowableTaskStats 資料量
print('\n6. FlowableTaskStats 資料量:')
try:
    result = ext.query("SELECT count() FROM FlowableTaskStats")
    print(f'   筆數: {result.result_rows[0][0]:,}')
except Exception as e:
    print(f'   錯誤: {e}')

# 7. 檢查外部系統的 TaskStatus 分布
print('\n7. FlowableTaskStats 的 TaskStatus 分布:')
try:
    result = ext.query('''
        SELECT TaskStatus, count() AS cnt
        FROM FlowableTaskStats
        GROUP BY TaskStatus
        ORDER BY cnt DESC
    ''')
    for row in result.result_rows:
        print(f'   {row[0]}: {row[1]:,}')
except Exception as e:
    print(f'   錯誤: {e}')

# 8. 檢查外部系統的 TaskBypass 分布
print('\n8. FlowableTaskStats 的 TaskBypass 分布:')
try:
    result = ext.query('''
        SELECT TaskBypass, count() AS cnt
        FROM FlowableTaskStats
        GROUP BY TaskBypass
        ORDER BY cnt DESC
    ''')
    for row in result.result_rows:
        print(f'   {row[0]}: {row[1]:,}')
except Exception as e:
    print(f'   錯誤: {e}')

# 9. 檢查外部系統的 TaskDefinitionKey 前綴分布
print('\n9. FlowableTaskStats 的 TaskDefinitionKey 前綴分布:')
try:
    result = ext.query('''
        SELECT 
            substring(TaskDefinitionKey, 1, 2) AS prefix,
            count() AS cnt
        FROM FlowableTaskStats
        WHERE TaskDefinitionKey IS NOT NULL
        GROUP BY prefix
        ORDER BY cnt DESC
        LIMIT 10
    ''')
    for row in result.result_rows:
        print(f'   {row[0]}: {row[1]:,}')
except Exception as e:
    print(f'   錯誤: {e}')

# 10. 檢查外部系統是否有排除 E/C 開頭的任務
print('\n10. 檢查 E/C 開頭的任務:')
try:
    result = ext.query('''
        SELECT 
            substring(TaskDefinitionKey, 1, 1) AS first_char,
            count() AS cnt
        FROM FlowableTaskStats
        WHERE TaskDefinitionKey LIKE 'E%' OR TaskDefinitionKey LIKE 'C%'
        GROUP BY first_char
    ''')
    for row in result.result_rows:
        print(f'   {row[0]} 開頭: {row[1]:,}')
except Exception as e:
    print(f'   錯誤: {e}')
