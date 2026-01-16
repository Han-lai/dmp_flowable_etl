#!/usr/bin/env python3
"""重建 FlowableTaskStats 表 - 分批插入"""

import clickhouse_connect

c = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

print('=== 重建 bronze.common_flowable_task_stats ===')

# 先刪除舊表
c.command('DROP TABLE IF EXISTS bronze.common_flowable_task_stats')

# 先建立表結構（從 MSSQL 取得 schema）
print('1. 建立表結構...')
create_sql = """
CREATE TABLE bronze.common_flowable_task_stats
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY tuple()
SETTINGS allow_nullable_key = 1
AS SELECT *, now64(3) as _sync_time 
FROM jdbc('mssql_master', 'SELECT TOP 1 * FROM APP_SRV_COMMON.dbo.FlowableTaskStats')
"""
c.command(create_sql)

# 清空表
c.command('TRUNCATE TABLE bronze.common_flowable_task_stats')

# 分批插入
print('2. 分批插入資料...')
batch_size = 100000
offset = 0
total = 0

while True:
    insert_sql = f"""
    INSERT INTO bronze.common_flowable_task_stats
    SELECT *, now64(3) as _sync_time 
    FROM jdbc('mssql_master', '
        SELECT * FROM APP_SRV_COMMON.dbo.FlowableTaskStats
        ORDER BY Id
        OFFSET {offset} ROWS FETCH NEXT {batch_size} ROWS ONLY
    ')
    """
    c.command(insert_sql)
    
    # 檢查這批插入了多少
    count_sql = f"""
    SELECT count() FROM jdbc('mssql_master', '
        SELECT 1 FROM APP_SRV_COMMON.dbo.FlowableTaskStats
        ORDER BY Id
        OFFSET {offset} ROWS FETCH NEXT {batch_size} ROWS ONLY
    ')
    """
    result = c.query(count_sql)
    batch_count = result.result_rows[0][0]
    total += batch_count
    
    print(f'   Offset {offset:,}: 插入 {batch_count:,} 筆 (累計 {total:,})')
    
    if batch_count < batch_size:
        break
    
    offset += batch_size

# 驗證
result = c.query('SELECT count() FROM bronze.common_flowable_task_stats')
print(f'\n3. 驗證: ClickHouse 共 {result.result_rows[0][0]:,} 筆')
