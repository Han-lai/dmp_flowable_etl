#!/usr/bin/env python3
"""比較狀態計算邏輯"""

import clickhouse_connect

local = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

ext = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

print('=== 比較狀態計算邏輯 ===')

# 1. 本地系統的 task_status 來源
print('\n1. 本地系統的 task_status 來源:')
print('   直接使用 bronze.common_flowable_task_stats.TaskStatus')
print('   這是任務的「最終狀態」，不是「某一天的狀態」')

# 2. 外部系統的 state_on_date 計算邏輯
print('\n2. 外部系統的 state_on_date 計算邏輯:')
print('''   multiIf(
       (delete_reason IS NOT NULL) AND (toDate(end_time) <= snapshot_date), 'TERMINATED',
       (end_time IS NOT NULL) AND (toDate(end_time) <= snapshot_date), 'DONE',
       (claim_time IS NOT NULL) AND (toDate(claim_time) <= snapshot_date), 'DOING',
       'TODO'
   )
   這是計算「在 snapshot_date 那天，任務的狀態是什麼」
''')

# 3. 舉例說明差異
print('3. 舉例說明差異:')
print('   假設一個任務:')
print('   - 2025-12-28 建立 (start_time)')
print('   - 2025-12-29 認領 (claim_time)')
print('   - 2025-12-30 完成 (end_time)')
print('   - 最終狀態: DONE')
print('')
print('   本地系統 (2025-12-28 快照):')
print('   - task_status = DONE (最終狀態)')
print('   - 計入 DONE 計數')
print('')
print('   外部系統 (2025-12-28 快照):')
print('   - state_on_date = TODO (因為 claim_time > 2025-12-28)')
print('   - 計入 TODO 計數')

# 4. 驗證：檢查 Bronze 層的 TaskStatus 分布
print('\n4. Bronze 層的 TaskStatus 分布:')
result = local.query('''
    SELECT TaskStatus, count() AS cnt
    FROM bronze.common_flowable_task_stats
    GROUP BY TaskStatus
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 5. 檢查 Bronze 層是否有 TaskCreateTime, TaskClaimTime, TaskEndTime
print('\n5. Bronze 層的時間欄位:')
result = local.query('''
    SELECT 
        count() AS total,
        countIf(TaskCreateTime IS NOT NULL) AS has_create,
        countIf(TaskClaimTime IS NOT NULL) AS has_claim,
        countIf(TaskEndTime IS NOT NULL) AS has_end
    FROM bronze.common_flowable_task_stats
''')
row = result.result_rows[0]
print(f'   總數: {row[0]:,}')
print(f'   有 TaskCreateTime: {row[1]:,}')
print(f'   有 TaskClaimTime: {row[2]:,}')
print(f'   有 TaskEndTime: {row[3]:,}')

# 6. 檢查 2025-12-28 建立的任務，在那天的狀態分布
print('\n6. 2025-12-28 建立的任務，在那天的狀態分布:')
result = local.query('''
    SELECT 
        -- 計算在 2025-12-28 那天的狀態
        multiIf(
            TaskEndTime IS NOT NULL AND toDate(TaskEndTime) <= toDate('2025-12-28'), 'DONE',
            TaskClaimTime IS NOT NULL AND toDate(TaskClaimTime) <= toDate('2025-12-28'), 'DOING',
            'TODO'
        ) AS state_on_date,
        count() AS cnt
    FROM bronze.common_flowable_task_stats
    WHERE TaskCreateDate = '2025-12-28'
    GROUP BY state_on_date
    ORDER BY cnt DESC
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,}')

# 7. 對比：最終狀態 vs 當天狀態
print('\n7. 對比：最終狀態 vs 當天狀態 (2025-12-28 建立的任務):')
result = local.query('''
    SELECT 
        TaskStatus AS final_status,
        multiIf(
            TaskEndTime IS NOT NULL AND toDate(TaskEndTime) <= toDate('2025-12-28'), 'DONE',
            TaskClaimTime IS NOT NULL AND toDate(TaskClaimTime) <= toDate('2025-12-28'), 'DOING',
            'TODO'
        ) AS state_on_date,
        count() AS cnt
    FROM bronze.common_flowable_task_stats
    WHERE TaskCreateDate = '2025-12-28'
    GROUP BY final_status, state_on_date
    ORDER BY cnt DESC
''')
print(f'   {"最終狀態":<15} {"當天狀態":<15} {"數量":<10}')
print('   ' + '-' * 40)
for row in result.result_rows:
    print(f'   {row[0]:<15} {row[1]:<15} {row[2]:,}')
