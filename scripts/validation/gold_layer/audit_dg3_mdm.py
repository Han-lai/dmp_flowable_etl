import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

print("=== DG3 MDM Overview (Grouped by Region and Factory) ===")
q1 = """
SELECT 
    region_code, 
    factory_code, 
    count() as line_count
FROM bronze.common_mdm_line_desc_master
WHERE plant_code = 'DG3'
GROUP BY region_code, factory_code
ORDER BY region_code, factory_code
"""
df1 = pd.DataFrame(client.query(q1).result_rows, columns=client.query(q1).column_names)
print(df1.to_string(index=False))

print("\n=== DG3 SMT Lines Detail ===")
q2 = """
SELECT 
    line_name, 
    region_code
FROM bronze.common_mdm_line_desc_master
WHERE plant_code = 'DG3' AND factory_code = 'SMT'
ORDER BY line_name
"""
df2 = pd.DataFrame(client.query(q2).result_rows, columns=client.query(q2).column_names)
print(df2.to_string(index=False))
