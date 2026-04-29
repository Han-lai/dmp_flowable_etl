import clickhouse_connect
import csv
import datetime

ch = clickhouse_connect.get_client(host='REDACTED_IP', port=8123, username='default', password='REDACTED_PASSWORD', database='default')

q = """
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
    t.ID_ as task_id,
    t.NAME_ as task_name,
    t.TASK_DEF_KEY_ as task_def_key,
    t.START_TIME_ as start_time,
    t.CLAIM_TIME_ as claim_time,
    t.END_TIME_ as end_time,
    t.ASSIGNEE_ as assignee,
    v.v_plant, v.v_factory, v.v_line, v.v_mo
FROM bronze.bpm_act_hi_taskinst t
JOIN var_pivot v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
WHERE t.START_TIME_ >= '2025-12-29 00:00:00' AND t.START_TIME_ <= '2025-12-31 23:59:59'
  AND v.v_plant = 'WJ2' AND v.v_factory = 'NBU' AND v.v_line = 'E5'
"""

rows = ch.query(q).result_rows

def is_null(dt):
    return dt is None or dt.year == 1970

boundary = datetime.datetime(2026, 1, 4, 23, 59, 59)

q_silver = """
SELECT task_id, status_weekly 
FROM silver.mv_fact_ui_task_details FINAL 
WHERE vx_type = 'V3' AND is_excluded = 0 
  AND toDate(task_start_time) BETWEEN '2025-12-29' AND '2025-12-31'
"""
silver_v3 = {r[0]: r[1] for r in ch.query(q_silver).result_rows}

missing_todo = []
missing_done = []
missing_doing = []

for row in rows:
    tid, tname, tkey, tstart, tclaim, tend, assignee, vplant, vfactory, vline, vmo = row
    
    # Calculate Weekly Status
    if not is_null(tend) and tend <= boundary:
        status = 'DONE'
    elif not is_null(tclaim) and tclaim <= boundary:
        status = 'DOING'
    else:
        status = 'TODO'
        
    if tid not in silver_v3:
        if status == 'DONE': missing_done.append(row)
        elif status == 'DOING': missing_doing.append(row)
        elif status == 'TODO': missing_todo.append(row)

print(f"Extracted {len(rows)} raw tasks from Bronze.")
print(f"Potential Missing TODO (in Bronze but not in Silver V3): {len(missing_todo)}")
print(f"Potential Missing DONE (in Bronze but not in Silver V3): {len(missing_done)}")
print(f"Potential Missing DOING (in Bronze but not in Silver V3): {len(missing_doing)}")

print("\n--- TODO Missing Details ---")
for t in missing_todo:
    print(f"ID: {t[0]} | Name: {t[1]} | Def: {t[2]} | Start: {t[3]}")

print("\n--- DONE Missing Details ---")
for t in missing_done:
    print(f"ID: {t[0]} | Name: {t[1]} | Def: {t[2]} | End: {t[5]}")
