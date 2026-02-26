import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

q = """
SELECT DISTINCT
    ld.LINE_NAME as line_name,
    pm.FACTORY as plant_code,
    pm.MFG_PLANT_CODE as factory_code,
    fa.REGION as fa_region,
    fa.MFG_SITE as fa_mfg_site_used_as_region
FROM bronze.common_mdm_line_desc_master ld
LEFT JOIN bronze.common_mdm_prod_area_master pa ON ld.PROD_AREA_ID = pa.PROD_AREA_ID
LEFT JOIN bronze.common_mdm_mfg_plant_master pm ON pa.MFG_PLANT_ID = pm.MFG_PLANT_ID
LEFT JOIN bronze.common_mdm_factory_area_master fa ON pa.FACTORY = fa.FACTORY
WHERE pm.FACTORY = 'DG3' AND pm.MFG_PLANT_CODE = 'SMT'
ORDER BY line_name
"""
print("=== Output from MDM JOIN for DG3 SMT ===")
df = pd.DataFrame(client.query(q).result_rows, columns=client.query(q).column_names)
print(df.to_string(index=False))
