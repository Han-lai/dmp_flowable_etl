import clickhouse_connect

ch = clickhouse_connect.get_client(host='REDACTED_IP', port=8123, username='default', password='REDACTED_PASSWORD', database='default')

base_filter = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3'"

print('--- [1] Daily Data (2025-12-25 ~ 2025-12-31) ---')
q_day = f'''
SELECT 
    snapshot_date,
    bitmapCardinality(groupBitmapMergeState(total_task)) as total,
    bitmapCardinality(groupBitmapMergeState(todo_daily)) as todo,
    bitmapCardinality(groupBitmapMergeState(doing_daily)) as doing,
    bitmapCardinality(groupBitmapMergeState(done_daily)) as done
FROM gold.rmv_l5_task_completion
WHERE {base_filter} AND snapshot_date BETWEEN '2025-12-25' AND '2025-12-31'
GROUP BY snapshot_date ORDER BY snapshot_date
'''
for row in ch.query(q_day).result_rows:
    print(row)

print('\n--- [2] Weekly Data (W52 & W1) ---')
q_week = f'''
SELECT 
    iso_year, iso_week,
    bitmapCardinality(groupBitmapMergeState(total_task)) as total,
    bitmapCardinality(groupBitmapMergeState(todo_weekly)) as todo,
    bitmapCardinality(groupBitmapMergeState(doing_weekly)) as doing,
    bitmapCardinality(groupBitmapMergeState(done_weekly)) as done
FROM gold.rmv_l5_task_completion
WHERE {base_filter} 
  AND ( (iso_year = 2025 AND iso_week = 52) OR (iso_year = 2026 AND iso_week = 1) )
GROUP BY iso_year, iso_week ORDER BY iso_year, iso_week
'''
for row in ch.query(q_week).result_rows:
    print(row)

print('\n--- [3] Monthly Data (Dec.) ---')
q_month = f'''
SELECT 
    iso_year, iso_month,
    bitmapCardinality(groupBitmapMergeState(total_task)) as total,
    bitmapCardinality(groupBitmapMergeState(todo_monthly)) as todo,
    bitmapCardinality(groupBitmapMergeState(doing_monthly)) as doing,
    bitmapCardinality(groupBitmapMergeState(done_monthly)) as done
FROM gold.rmv_l5_task_completion
WHERE {base_filter} AND iso_year = 2025 AND iso_month = 12
GROUP BY iso_year, iso_month
'''
for row in ch.query(q_month).result_rows:
    print(row)
