import clickhouse_connect
import datetime

ch = clickhouse_connect.get_client(host='REDACTED_IP', port=8123, username='default', password='REDACTED_PASSWORD', database='default')

q_bronze = """
WITH var_pivot AS (
    SELECT 
        PROC_INST_ID_,
        max(case when NAME_ = 'plant' then TEXT_ end) as v_plant,
        max(case when NAME_ = 'factory' then TEXT_ end) as v_factory,
        max(case when NAME_ = 'lineName' then TEXT_ end) as v_line,
        max(case when NAME_ = 'moNumber' then TEXT_ end) as v_mo
    FROM bronze.bpm_act_hi_varinst
    GROUP BY PROC_INST_ID_
)
SELECT 
    t.ID_, t.NAME_, t.TASK_DEF_KEY_, v.v_mo, t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_, t.ASSIGNEE_, 
    he.EmpName as assignee_name
FROM bronze.bpm_act_hi_taskinst t
JOIN var_pivot v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
LEFT JOIN bronze.common_hr_employee AS he ON t.ASSIGNEE_ = he.EmpCode
WHERE t.START_TIME_ BETWEEN '2025-12-29 00:00:00' AND '2025-12-31 23:59:59'
  AND v.v_plant = 'WJ2' AND v.v_factory = 'NBU' AND v.v_line = 'E5'
"""

bronze_tasks = ch.query(q_bronze).result_rows

q_silver = """
SELECT task_id, vx_type, is_excluded, exclude_reason, status_weekly
FROM silver.mv_fact_ui_task_details FINAL
WHERE toDate(task_start_time) BETWEEN '2025-12-29' AND '2025-12-31'
  AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
"""
silver_map = {r[0]: (r[1], r[2], r[3], r[4]) for r in ch.query(q_silver).result_rows}

def is_null(dt):
    return dt is None or dt.year == 1970

boundary = datetime.datetime(2026, 1, 4, 23, 59, 59)

def get_status(claim, end):
    if not is_null(end) and end <= boundary: return 'DONE'
    if not is_null(claim) and claim <= boundary: return 'DOING'
    return 'TODO'

discrepancy_todo = [] # In Bronze as TODO, but not in Silver V3 (0)
discrepancy_done = [] # In Bronze as DONE, but not in Silver V3 (0)

for bt in bronze_tasks:
    tid, tname, tkey, tmo, tstart, tclaim, tend, assignee, aname = bt
    status = get_status(tclaim, tend)
    
    if tid in silver_map:
        vxt, is_ex, reason, sw = silver_map[tid]
        # It IS in our result. If it's V3 and NOT excluded, it's already counted.
        # If it's NOT V3 or IS excluded, why?
        if vxt != 'V3' or is_ex == 1:
            if status == 'TODO': discrepancy_todo.append((bt, f"V4 categorized as {vxt}, Excluded={is_ex}, Reason={reason}"))
            if status == 'DONE': discrepancy_done.append((bt, f"V4 categorized as {vxt}, Excluded={is_ex}, Reason={reason}"))
    else:
        # NOT in Silver at all!
        if status == 'TODO': discrepancy_todo.append((bt, "Missing from Silver entirely"))
        if status == 'DONE': discrepancy_done.append((bt, "Missing from Silver entirely"))

print(f"Total Bronze: {len(bronze_tasks)}")
print(f"Discrepancy TODO: {len(discrepancy_todo)}")
print(f"Discrepancy DONE: {len(discrepancy_done)}")

print("\n--- TODO Discrepancy Detail ---")
for t, msg in discrepancy_todo:
    print(f"ID: {t[0]} | Def: {t[2]} | MO: {t[3]} | Start: {t[4]} | Reason: {msg}")

print("\n--- DONE Discrepancy Detail ---")
for t, msg in discrepancy_done:
    print(f"ID: {t[0]} | Def: {t[2]} | MO: {t[3]} | End: {t[6]} | Reason: {msg}")
