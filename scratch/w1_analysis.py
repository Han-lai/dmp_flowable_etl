import clickhouse_connect
import datetime

ch = clickhouse_connect.get_client(host='10.146.206.76', port=8123, username='default', password='1qaz2wsx3edc', database='default')

# Boundary for W1
week_end = datetime.datetime(2026, 1, 4, 23, 59, 59)

q = """
WITH raw_tasks AS (
    SELECT
        t.ID_ AS task_id,
        t.NAME_ as task_name,
        t.START_TIME_ AS task_start_time,
        t.CLAIM_TIME_ AS task_claim_time,
        t.END_TIME_ AS task_end_time,
        t.TASK_DEF_KEY_ AS task_def_key,
        v_pivot.varinst_moNumber as mo_number,
        tb.LONG_ as is_autoComplete,
        he.EmpName as assignee_name
    FROM bronze.bpm_act_hi_taskinst AS t
    LEFT JOIN silver.mv_varinst_pivoted AS v_pivot ON t.PROC_INST_ID_ = v_pivot.PROC_INST_ID_
    LEFT JOIN silver.mv_dim_mfg_five_level AS mdm ON (v_pivot.varinst_lineName = mdm.line_name) AND (v_pivot.varinst_plant = mdm.plant_code)
    LEFT JOIN bronze.common_hr_employee AS he ON t.ASSIGNEE_ = he.EmpCode
    LEFT JOIN (
        SELECT TASK_ID_, LONG_
        FROM bronze.bpm_act_hi_varinst
        WHERE NAME_ = 'autoComplete' AND TASK_ID_ IS NOT NULL AND TASK_ID_ != ''
    ) AS tb ON t.ID_ = tb.TASK_ID_
    WHERE t.START_TIME_ >= '2025-12-29 00:00:00' AND t.START_TIME_ <= '2025-12-31 23:59:59'
      AND COALESCE(NULLIF(v_pivot.varinst_plant, ''), mdm.plant_code, '') = 'WJ2'
      AND COALESCE(NULLIF(v_pivot.varinst_factory, ''), mdm.factory_code, '') = 'NBU'
      AND COALESCE(NULLIF(v_pivot.varinst_lineName, ''), mdm.line_name, '') = 'E5'
      AND t.TASK_DEF_KEY_ LIKE 'V3%'
)
SELECT * FROM raw_tasks
"""

results = ch.query(q).result_rows

def get_status_weekly(start_time, claim_time, end_time, boundary):
    # NULL treatment (assuming 1970 is NULL)
    def is_null(dt):
        return dt is None or dt.year == 1970
    
    if not is_null(end_time) and end_time <= boundary:
        return 'DONE'
    if not is_null(claim_time) and claim_time <= boundary:
        return 'DOING'
    return 'TODO'

def check_excluded(task_name, task_def_key, mo_number, is_autoComplete, assignee_name):
    if is_autoComplete == 1: return True, "autoComplete=1"
    if assignee_name == "SYSTEM": return True, "assignee=SYSTEM"
    if task_def_key.startswith('E') or task_def_key.startswith('C'): return True, "E/C Node"
    if mo_number and (mo_number.startswith('Q') or mo_number.startswith('R')): return True, "Q/R Order"
    if task_name and any(x in task_name for x in ["通知", "Dummy", "Virtual"]): return True, "Notify/Dummy"
    return False, ""

v4_results = {"TODO": [], "DOING": [], "DONE": [], "EXCLUDED": []}

for row in results:
    tid, tname, tstart, tclaim, tend, tdef, mo, autocomp, aname = row
    
    is_ex, reason = check_excluded(tname, tdef, mo, autocomp, aname)
    status = get_status_weekly(tstart, tclaim, tend, week_end)
    
    if is_ex:
        v4_results["EXCLUDED"].append((tid, status, reason))
    else:
        v4_results[status].append(tid)

print(f"V4 Results (W1):")
print(f"  TODO: {len(v4_results['TODO'])}")
print(f"  DOING: {len(v4_results['DOING'])}")
print(f"  DONE: {len(v4_results['DONE'])}")
print(f"  EXCLUDED: {len(v4_results['EXCLUDED'])}")

# Now, if MSSQL TODO = 12 and DONE = 440 (Total 452)
# And our TODO = 7 and DONE = 433 (Total 440)
# We need to find what tasks are in MSSQL but not in our TODO/DONE.
