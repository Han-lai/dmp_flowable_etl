import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
r = client.query("SELECT region_code, plant_code, factory_code, line_name, count() as c FROM silver.mv_dim_mfg_five_level WHERE plant_code='DG3' AND factory_code='SMT' GROUP BY region_code, plant_code, factory_code, line_name ORDER BY line_name")

print("--- DG3 SMT in silver.mv_dim_mfg_five_level ---")
df = pd.DataFrame(r.result_rows, columns=r.column_names)
print(df.to_string(index=False))
