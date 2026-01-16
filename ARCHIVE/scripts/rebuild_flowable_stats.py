#!/usr/bin/env python3
"""重建 FlowableTaskStats 表"""

import clickhouse_connect

c = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default'
)

print('重建 bronze.common_flowable_task_stats...')
c.command('DROP TABLE IF EXISTS bronze.common_flowable_task_stats')

sql = """
CREATE TABLE bronze.common_flowable_task_stats
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY tuple()
SETTINGS allow_nullable_key = 1
AS SELECT *, now64(3) as _sync_time 
FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.FlowableTaskStats')
"""
c.command(sql)

result = c.query('SELECT count() FROM bronze.common_flowable_task_stats')
print(f'同步完成: {result.result_rows[0][0]:,} 筆')
