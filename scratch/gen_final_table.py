import clickhouse_connect

ch = clickhouse_connect.get_client(host='10.146.206.76', port=8123, username='default', password='1qaz2wsx3edc', database='default')

base_filter = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3'"

def format_num(val):
    return f"{int(val):,}"

final_table = []

# 1. Month: Dec (月底結算)
# Filter by calendar_year to include 12/29-12/31 correctly
q_month = f'''
SELECT 
    bitmapCardinality(groupBitmapMergeState(total_task)) as total,
    bitmapCardinality(groupBitmapMergeState(todo_monthly)) as todo,
    bitmapCardinality(groupBitmapMergeState(doing_monthly)) as doing,
    bitmapCardinality(groupBitmapMergeState(done_monthly)) as done,
    bitmapCardinality(groupBitmapMergeState(acc)) as acc
FROM gold.rmv_l5_task_completion
WHERE {base_filter} AND calendar_year = 2025 AND iso_month = 12
'''
for r in ch.query(q_month).result_rows:
    final_table.append(["Month", "Dec. (月底結算)", format_num(r[0]), format_num(r[1]), format_num(r[2]), format_num(r[3]), format_num(r[4])])

# 2. Weeks (W1, W52, W51)
# W1 is 2026-W1
# W52 is 2025-W52
# W51 is 2025-W51
weeks = [(2026, 1, "W1 (週末結算)"), (2025, 52, "W52 (週末結算)"), (2025, 51, "W51 (週末結算)")]
for y, w, name in weeks:
    q_week = f'''
    SELECT 
        bitmapCardinality(groupBitmapMergeState(total_task)) as total,
        bitmapCardinality(groupBitmapMergeState(todo_weekly)) as todo,
        bitmapCardinality(groupBitmapMergeState(doing_weekly)) as doing,
        bitmapCardinality(groupBitmapMergeState(done_weekly)) as done,
        bitmapCardinality(groupBitmapMergeState(acc)) as acc
    FROM gold.rmv_l5_task_completion
    WHERE {base_filter} AND iso_year = {y} AND iso_week = {w}
    '''
    for r in ch.query(q_week).result_rows:
        final_table.append(["Week", name, format_num(r[0]), format_num(r[1]), format_num(r[2]), format_num(r[3]), format_num(r[4])])

# 3. Days (12/31 ~ 12/25)
q_day = f'''
SELECT 
    formatDateTime(snapshot_date, '%m/%d (當日結算)') as period_name,
    bitmapCardinality(groupBitmapMergeState(total_task)) as total,
    bitmapCardinality(groupBitmapMergeState(todo_daily)) as todo,
    bitmapCardinality(groupBitmapMergeState(doing_daily)) as doing,
    bitmapCardinality(groupBitmapMergeState(done_daily)) as done,
    bitmapCardinality(groupBitmapMergeState(acc)) as acc
FROM gold.rmv_l5_task_completion
WHERE {base_filter} AND snapshot_date BETWEEN '2025-12-25' AND '2025-12-31'
GROUP BY snapshot_date
ORDER BY snapshot_date DESC
'''
for r in ch.query(q_day).result_rows:
    final_table.append(["Day", r[0], format_num(r[1]), format_num(r[2]), format_num(r[3]), format_num(r[4]), format_num(r[5])])

# Print table
print("| 粒度 | 週期/日期 | Total Task | Todo | Doing | Done | ACC (WIP) |")
print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
for row in final_table:
    print("| " + " | ".join(row) + " |")
