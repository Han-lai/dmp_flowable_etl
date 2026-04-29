import clickhouse_connect
import csv

ch = clickhouse_connect.get_client(host='REDACTED_IP', port=8123, username='default', password='REDACTED_PASSWORD', database='default')

start_ts = '2025-12-29 00:00:00'
end_ts = '2025-12-31 23:59:59'

# End of week for W1 (2025-12-29 is Monday)
week_end = '2026-01-04 23:59:59'

q = f"""
WITH raw_tasks AS (
    SELECT
        t.ID_ AS task_id,
        t.START_TIME_ AS task_start_time,
        t.CLAIM_TIME_ AS task_claim_time,
        t.END_TIME_ AS task_end_time,
        t.ASSIGNEE_ AS assignee,
        t.TASK_DEF_KEY_ AS task_def_key,
        v_pivot.varinst_moNumber as mo_number,
        COALESCE(NULLIF(v_pivot.varinst_region, ''), mdm.region_code, plant_mdm.region_code, 'UNKNOWN') AS region,
        COALESCE(NULLIF(v_pivot.varinst_plant, ''), mdm.plant_code, 'UNKNOWN') AS plant,
        COALESCE(NULLIF(v_pivot.varinst_factory, ''), mdm.factory_code, 'UNKNOWN') AS factory,
        COALESCE(NULLIF(v_pivot.varinst_lineName, ''), mdm.line_name, 'UNKNOWN') AS line,
        tb.LONG_ as is_autoComplete,
        he.EmpName as assignee_name
    FROM bronze.bpm_act_hi_taskinst AS t
    LEFT JOIN silver.mv_varinst_pivoted AS v_pivot ON t.PROC_INST_ID_ = v_pivot.PROC_INST_ID_
    LEFT JOIN silver.mv_dim_mfg_five_level AS mdm ON (v_pivot.varinst_lineName = mdm.line_name) AND (v_pivot.varinst_plant = mdm.plant_code)
    LEFT JOIN (
        SELECT DISTINCT plant_code, region_code 
        FROM silver.mv_dim_mfg_five_level 
        WHERE plant_code != '' AND region_code IS NOT NULL
    ) AS plant_mdm ON COALESCE(NULLIF(v_pivot.varinst_plant, ''), mdm.plant_code, '') = plant_mdm.plant_code
    LEFT JOIN bronze.common_hr_employee AS he ON t.ASSIGNEE_ = he.EmpCode
    LEFT JOIN (
        SELECT TASK_ID_, LONG_
        FROM bronze.bpm_act_hi_varinst
        WHERE NAME_ = 'autoComplete' AND TASK_ID_ IS NOT NULL AND TASK_ID_ != ''
    ) AS tb ON t.ID_ = tb.TASK_ID_
    WHERE t.START_TIME_ >= '{start_ts}' AND t.START_TIME_ <= '{end_ts}'
)
SELECT 
    task_id, task_start_time, task_claim_time, task_end_time,
    task_def_key, mo_number,
    region, plant, factory, line,
    is_autoComplete, assignee_name
FROM raw_tasks
WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
  AND (task_def_key LIKE 'V3%%')
"""

rows = ch.query(q).result_rows
header = ['task_id', 'start_time', 'claim_time', 'end_time', 'task_def_key', 'mo_number', 'region', 'plant', 'factory', 'line', 'is_autoComplete', 'assignee_name']

with open('scratch/w1_raw_comparison.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(rows)

print(f"Exported {len(rows)} raw tasks to scratch/w1_raw_comparison.csv")
