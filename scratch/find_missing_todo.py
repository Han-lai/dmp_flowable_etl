import clickhouse_connect
import datetime

ch = clickhouse_connect.get_client(host='10.146.206.76', port=8123, username='default', password='1qaz2wsx3edc', database='default')

q_bronze = """
WITH var_pivot AS (
    SELECT 
        PROC_INST_ID_,
        max(case when NAME_ = 'plant' then TEXT_ end) as v_plant,
        max(case when NAME_ = 'factory' then TEXT_ end) as v_factory,
        max(case when NAME_ = 'lineName' then TEXT_ end) as v_line
    FROM bronze.bpm_act_hi_varinst
    GROUP BY PROC_INST_ID_
)
SELECT t.ID_, t.NAME_, t.TASK_DEF_KEY_, t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_, he.EmpName
FROM bronze.bpm_act_hi_taskinst t
JOIN var_pivot v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
LEFT JOIN bronze.common_hr_employee AS he ON t.ASSIGNEE_ = he.EmpCode
WHERE t.START_TIME_ BETWEEN '2025-12-29 00:00:00' AND '2025-12-31 23:59:59'
  AND v.v_plant = 'WJ2' AND v.v_factory = 'NBU' AND v.v_line = 'E5'
  AND t.TASK_DEF_KEY_ LIKE 'V3%'
"""

# Tasks in Silver V3 TODO (not excluded)
q_silver = "SELECT task_id FROM silver.mv_fact_ui_task_details FINAL WHERE vx_type = 'V3' AND is_excluded = 0 AND status_weekly = 'TODO'"
silver_todo = {r[0] for r in ch.query(q_silver).result_rows}

def is_null(dt):
    return dt is None or dt.year == 1970

boundary = datetime.datetime(2026, 1, 4, 23, 59, 59)

bronze_tasks = ch.query(q_bronze).result_rows
missing_todo = []
for tid, tname, tkey, tstart, tclaim, tend, aname in bronze_tasks:
    # Weekly Cohort Status calculation
    if not is_null(tend) and tend <= boundary:
        status = 'DONE'
    elif not is_null(tclaim) and tclaim <= boundary:
        status = 'DOING'
    else:
        status = 'TODO'
    
    if status == 'TODO' and tid not in silver_todo:
        missing_todo.append((tid, tname, tkey, aname))

print(f"Total Missing TODO: {len(missing_todo)}")
for m in missing_todo:
    print(m)
