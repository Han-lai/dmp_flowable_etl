import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

print("=== Silver Tables Metadata ===")
r = client.query("SELECT name, engine, total_rows FROM system.tables WHERE database='silver'")
df = pd.DataFrame(r.result_rows, columns=r.column_names)
print(df.to_string())

print("\n=== Gold Tables Metadata ===")
r = client.query("SELECT name, engine, total_rows FROM system.tables WHERE database='gold'")
df = pd.DataFrame(r.result_rows, columns=r.column_names)
print(df.to_string())
