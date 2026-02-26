import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

q = """
SELECT 
    ld.LINE_NAME as line_name,
    pa.PROD_AREA_ID as prod_area_id_in_pa_table,
    ld.PROD_AREA_ID as prod_area_id_in_ld_table
FROM bronze.common_mdm_line_desc_master ld
LEFT JOIN bronze.common_mdm_prod_area_master pa ON ld.PROD_AREA_ID = pa.PROD_AREA_ID
WHERE ld.LINE_NAME IN ('ST01', 'ST02', 'ST03', 'ST04', 'ST05', 'ST06')
ORDER BY ld.LINE_NAME
"""
r = client.query(q)
df = pd.DataFrame(r.result_rows, columns=r.column_names)
print(df.to_string(index=False))
