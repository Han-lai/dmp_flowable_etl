#!/usr/bin/env python3
"""檢查 FlowableTaskStats 資料"""

import clickhouse_connect

c = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

# 檢查 MSSQL 來源表
print('=== MSSQL FlowableTaskStats ===')
result = c.query("SELECT count() FROM jdbc('mssql_master', 'SELECT 1 FROM APP_SRV_COMMON.dbo.FlowableTaskStats')")
print(f'MSSQL 筆數: {result.result_rows[0][0]:,}')

# 檢查 ClickHouse 目標表
print('\n=== ClickHouse bronze.common_flowable_task_stats ===')
result = c.query('SELECT count() FROM bronze.common_flowable_task_stats')
print(f'ClickHouse 筆數: {result.result_rows[0][0]:,}')
