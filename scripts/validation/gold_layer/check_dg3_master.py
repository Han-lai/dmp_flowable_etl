import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

r = client.query("DESCRIBE TABLE bronze.common_mdm_line_desc_master")
print([row[0] for row in r.result_rows])

print("\n--- Region sources for DG3 in Silver Fact Table ---")
q3 = """
SELECT region, region_source, plant, factory, line, count() as cnt
FROM silver.mv_fact_task_vx
WHERE plant = 'DG3'
GROUP BY region, region_source, plant, factory, line
ORDER BY cnt DESC
LIMIT 20
"""
df = pd.DataFrame(client.query(q3).result_rows, columns=client.query(q3).column_names)
print(df.to_string(index=False))
