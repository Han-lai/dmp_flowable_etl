import clickhouse_connect

ch = clickhouse_connect.get_client(host='REDACTED_IP', port=8123, username='default', password='REDACTED_PASSWORD', database='default')

base_filter = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3'"

def get_row(gran, period, total, todo, doing, done, acc):
    return [gran, period, f"{total:,}", f"{todo:,}", f"{doing:,}", f"{done:,}", f"{acc:,}"]

final_table = []

# Month
q_month = f'''
SELECT 
    'Month' as granularity, 'Dec. (月底結算)' as period_name,
    bitmapCardinality(groupBitmapMergeState(total_task)) as total,
    bitmapCardinality(groupBitmapMergeState(todo_monthly)) as todo,
    bitmapCardinality(groupBitmapMergeState(doing_monthly)) as doing,
    bitmapCardinality(groupBitmapMergeState(done_monthly)) as done,
    bitmapCardinality(groupBitmapMergeState(acc)) as acc
FROM gold.rmv_l5_task_completion
WHERE {base_filter} AND iso_year = 2025 AND iso_month = 12
'''
for r in ch.query(q_month).result_rows:
    final_table.append(get_row(*r))

# Weeks (W1, W52, W51)
q_week = f'''
SELECT 
    'Week' as granularity, 
    CASE WHEN iso_week = 1 THEN 'W1 (週末結算)' ELSE concat('W', toString(iso_week), ' (週末結算)') END as period_name,
    bitmapCardinality(groupBitmapMergeState(total_task)) as total,
    bitmapCardinality(groupBitmapMergeState(todo_weekly)) as todo,
    bitmapCardinality(groupBitmapMergeState(doing_weekly)) as doing,
    bitmapCardinality(groupBitmapMergeState(done_weekly)) as done,
    bitmapCardinality(groupBitmapMergeState(acc)) as acc,
    iso_year, iso_week
FROM gold.rmv_l5_task_completion
WHERE {base_filter} 
  AND ( (iso_year = 2025 AND iso_week IN (51, 52)) OR (iso_year = 2026 AND iso_week = 1) )
GROUP BY iso_year, iso_week
ORDER BY iso_year DESC, iso_week DESC
'''
for r in ch.query(q_week).result_rows:
    final_table.append(get_row(r[0], r[1], r[2], r[3], r[4], r[5], r[6]))

# Days (12/31 ~ 12/25)
q_day = f'''
SELECT 
    'Day' as granularity, formatDateTime(snapshot_date, '%m/%d (當日結算)') as period_name,
    bitmapCardinality(groupBitmapMergeState(total_task)) as total,
    bitmapCardinality(groupBitmapMergeState(todo_daily)) as todo,
    bitmapCardinality(groupBitmapMergeState(doing_daily)) as doing,
    bitmapCardinality(groupBitmapMergeState(done_daily)) as done,
    bitmapCardinality(groupBitmapMergeState(acc)) as acc,
    snapshot_date
FROM gold.rmv_l5_task_completion
WHERE {base_filter} AND snapshot_date BETWEEN '2025-12-25' AND '2025-12-31'
GROUP BY snapshot_date
ORDER BY snapshot_date DESC
'''
for r in ch.query(q_day).result_rows:
    final_table.append(get_row(r[0], r[1], r[2], r[3], r[4], r[5], r[6]))

# Print as Markdown Table
print("| 粒度 | 週期/日期 | Total Task | Todo | Doing | Done | ACC (WIP) |")
print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
for row in final_table:
    print("| " + " | ".join(row) + " |")
