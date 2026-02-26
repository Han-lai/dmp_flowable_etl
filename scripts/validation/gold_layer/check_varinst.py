import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

q = """
SELECT 
    varinst_region, varinst_plant, varinst_factory, varinst_lineName, count() as cnt
FROM silver.mv_varinst_pivoted
WHERE varinst_lineName = 'ST02'
GROUP BY varinst_region, varinst_plant, varinst_factory, varinst_lineName
ORDER BY cnt DESC
LIMIT 10
"""
df = pd.DataFrame(client.query(q).result_rows, columns=client.query(q).column_names)
print(df.to_string(index=False))
