#!/usr/bin/env python3
"""
檢查 L5 指標相關表
"""
import clickhouse_connect

ch = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

print('=== L5 任務完成率快照表結構 ===')
desc = ch.query('DESCRIBE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT')
for row in desc.result_rows:
    print(f'  {row[0]:<25} {row[1]:<20}')

print('\n=== 表內容範例（前 3 筆）===')
sample = ch.query('SELECT * FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT ORDER BY snapshot_date DESC LIMIT 3')
for row in sample.result_rows:
    print(f'  {row}')

print('\n=== 統計資訊 ===')
stats = ch.query('SELECT count(*) as total_rows, min(snapshot_date) as min_date, max(snapshot_date) as max_date FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT')
for row in stats.result_rows:
    print(f'  總筆數: {row[0]}, 日期範圍: {row[1]} ~ {row[2]}')

print('\n=== Vx 類型分布 ===')
vx_dist = ch.query('SELECT vx_type, count(*) FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT GROUP BY vx_type ORDER BY count(*) DESC')
for row in vx_dist.result_rows:
    print(f'  {row[0]}: {row[1]} 筆')

print('\n=== task_detail_wide 統計 ===')
stats = ch.query("SELECT count(*) as total, countIf(task_bypass='N') as non_bypass FROM silver.task_detail_wide FINAL")
for row in stats.result_rows:
    print(f'  總筆數: {row[0]:,}, 非 bypass: {row[1]:,}')

print('\n=== 維度分布範例 ===')
dims = ch.query("SELECT plant, factory, line, count(*) FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT GROUP BY plant, factory, line ORDER BY count(*) DESC LIMIT 5")
for row in dims.result_rows:
    print(f'  {row[0]}/{row[1]}/{row[2]}: {row[3]} 筆')