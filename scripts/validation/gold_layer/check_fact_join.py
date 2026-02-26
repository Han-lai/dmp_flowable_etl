import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

q = """
SELECT 
    mv_varinst_pivoted.varinst_region as var_region,
    mv_varinst_pivoted.varinst_plant as var_plant,
    mv_varinst_pivoted.varinst_factory as var_factory,
    mv_varinst_pivoted.varinst_lineName as var_line,
    mdm.region_code as mdm_region,
    mdm.plant_code as mdm_plant,
    mdm.factory_code as mdm_factory,
    mdm.line_name as mdm_line,
    count() as cnt
FROM bronze.bpm_act_hi_taskinst t
LEFT JOIN silver.mv_varinst_pivoted ON t.PROC_INST_ID_ = mv_varinst_pivoted.PROC_INST_ID_
LEFT JOIN silver.mv_dim_mfg_five_level mdm ON mv_varinst_pivoted.varinst_lineName = mdm.line_name
WHERE mdm.plant_code = 'DG3' AND mdm.factory_code = 'SMT' AND mdm.line_name = 'ST02'
GROUP BY 
    var_region, var_plant, var_factory, var_line,
    mdm_region, mdm_plant, mdm_factory, mdm_line
ORDER BY cnt DESC
LIMIT 10
"""

df = pd.DataFrame(client.query(q).result_rows, columns=client.query(q).column_names)
print(df.to_string(index=False))
