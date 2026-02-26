import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

q = """
SELECT 
    t.ID_,
    mv_varinst_pivoted.varinst_lineName,
    mv_varinst_pivoted.varinst_plant,
    mdm.region_code,
    mdm.plant_code
FROM bronze.bpm_act_hi_taskinst t
LEFT JOIN silver.mv_varinst_pivoted ON t.PROC_INST_ID_ = mv_varinst_pivoted.PROC_INST_ID_
LEFT JOIN silver.mv_dim_mfg_five_level mdm ON mv_varinst_pivoted.varinst_lineName = mdm.line_name AND mv_varinst_pivoted.varinst_plant = mdm.plant_code
WHERE t.PROC_INST_ID_ IN (
    SELECT PROC_INST_ID_ FROM bronze.bpm_act_hi_varinst WHERE NAME_='lineName' AND TEXT_='ST02' LIMIT 5
)
LIMIT 5
"""
r = client.query(q)
for row in r.result_rows:
    print(row)
