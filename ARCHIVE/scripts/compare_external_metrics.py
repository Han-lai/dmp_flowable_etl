#!/usr/bin/env python3
"""比較外部 ClickHouse 與本地的差異"""

import clickhouse_connect

# 外部 ClickHouse 連線
ext = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8124, 
    username='ch_user', 
    password='ch_strong_password_change_me',
    database='flowable_analytics'
)

# 本地 ClickHouse 連線
local = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

print('=== 比較外部與本地 ClickHouse ===')

# 1. 外部系統的資料來源
print('\n1. 外部系統的表:')
result = ext.query("SHOW TABLES")
for row in result.result_rows:
    print(f'   {row[0]}')

# 2. 外部系統有資料的日期
print('\n2. 外部系統有實際資料的日期 (done_count > 0):')
result = ext.query('''
    SELECT 
        snapshot_date,
        sum(todo_count) AS todo,
        sum(doing_count) AS doing,
        sum(done_count) AS done,
        sum(created_count) AS created
    FROM gold_daily_task_metrics
    WHERE done_count > 0 OR doing_count > 0 OR todo_count > 0
    GROUP BY snapshot_date
    ORDER BY snapshot_date DESC
    LIMIT 10
''')
for row in result.result_rows:
    print(f'   {row[0]}: TODO={row[1]:,}, DOING={row[2]:,}, DONE={row[3]:,}, CREATED={row[4]:,}')

# 3. 外部系統的維度
print('\n3. 外部系統的維度 (有資料的):')
result = ext.query('''
    SELECT 
        proc_vx,
        count() AS cnt,
        sum(done_count) AS done
    FROM gold_daily_task_metrics
    WHERE done_count > 0
    GROUP BY proc_vx
    ORDER BY done DESC
    LIMIT 10
''')
for row in result.result_rows:
    print(f'   {row[0]}: {row[1]:,} 筆, done={row[2]:,}')

# 4. 外部系統的 task_def_key 格式
print('\n4. 外部系統的 task_def_key 格式 (有資料的):')
result = ext.query('''
    SELECT DISTINCT task_def_key
    FROM gold_daily_task_metrics
    WHERE done_count > 0
    LIMIT 10
''')
for row in result.result_rows:
    print(f'   {row[0]}')

# 5. 本地系統的 task_definition_key 格式
print('\n5. 本地系統的 task_definition_key 格式:')
result = local.query('''
    SELECT DISTINCT task_definition_key
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE is_excluded = 0
    LIMIT 10
''')
for row in result.result_rows:
    print(f'   {row[0]}')

# 6. 外部系統的概念分析
print('\n6. 外部系統的概念分析:')
print('   - snapshot_date: 快照日期')
print('   - proc_vx: 流程 Vx 歸屬 (V1/V2/V3)')
print('   - proc_region/plant/factory/line: 維度')
print('   - task_def_key: 任務定義 Key')
print('   - todo/doing/done/terminated/created: 各狀態計數')
print('   - 維度粒度: 日期 + Vx + 地區 + 廠區 + 產線 + 任務定義')

# 7. 本地系統的概念
print('\n7. 本地系統的概念:')
print('   - snapshot_date: 快照日期')
print('   - vx_type: Vx 歸屬 (V1/V2/V3)')
print('   - vx_subtype: V1 子分類 (V1_MFG/V1_NPE)')
print('   - plant/factory/line: 維度')
print('   - 維度粒度: 日期 + Vx + 子類型 + 廠區 + 產線')
print('   - 差異: 本地沒有 task_def_key 維度，但有 vx_subtype')
