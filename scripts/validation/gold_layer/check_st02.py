import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

q = """
SELECT 
    ld.LINE_NAME as line_name,
    ld.PROD_AREA_ID,
    pa.PROD_AREA_CODE,
    pa.FACTORY as pa_factory,
    pa.MFG_PLANT_ID,
    pm.MFG_PLANT_CODE,
    pm.FACTORY as pm_factory,
    fa.REGION,
    fa.MFG_SITE
FROM bronze.common_mdm_line_desc_master ld
LEFT JOIN bronze.common_mdm_prod_area_master pa ON ld.PROD_AREA_ID = pa.PROD_AREA_ID
LEFT JOIN bronze.common_mdm_mfg_plant_master pm ON pa.MFG_PLANT_ID = pm.MFG_PLANT_ID
LEFT JOIN bronze.common_mdm_factory_area_master fa ON pa.FACTORY = fa.FACTORY
WHERE ld.LINE_NAME = 'ST02'
"""
r = client.query(q)
df = pd.DataFrame(r.result_rows, columns=r.column_names)
print(df.to_string(index=False))
