import clickhouse_connect
import csv

ch = clickhouse_connect.get_client(host='10.146.206.76', port=8123, username='default', password='1qaz2wsx3edc', database='default')

# We'll extract everything for W1 (12/29 - 12/31) that matches WJ2/NBU/E5.
# We'll include both V3 and non-V3 to see if some V3 tasks are misclassified.

q = """
SELECT 
    task_id,
    task_name,
    task_definition_key,
    vx_type,
    task_status,
    is_excluded,
    exclude_reason,
    toDate(task_start_time) as start_date,
    task_claim_time,
    task_end_time,
    status_weekly
FROM silver.mv_fact_ui_task_details FINAL
WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
  AND toDate(task_start_time) BETWEEN '2025-12-29' AND '2025-12-31'
ORDER BY is_excluded, status_weekly, task_id
"""

rows = ch.query(q).result_rows
header = ['task_id', 'task_name', 'task_definition_key', 'vx_type', 'task_status', 'is_excluded', 'exclude_reason', 'start_date', 'claim_time', 'end_time', 'status_weekly']

with open('scratch/w1_audit_full.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(rows)

# Count distribution
counts = {}
for row in rows:
    vxt = row[3]
    ex = row[5]
    sw = row[10]
    key = (vxt, ex, sw)
    counts[key] = counts.get(key, 0) + 1

print("--- W1 Distribution (Plant=WJ2, Factory=NBU, Line=E5) ---")
print(f"{'VX Type':8s} | {'Excluded':8s} | {'Weekly Status':13s} | {'Count'}")
print("-" * 50)
for k, v in sorted(counts.items()):
    print(f"{k[0]:8s} | {str(k[1]):8s} | {k[2]:13s} | {v}")
