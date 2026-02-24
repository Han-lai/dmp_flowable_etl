
import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

tables = ['default.DMPFunctionConfig', 'default.DMPFunctionClientMapping']

for table in tables:
    try:
        result = client.command(f"SHOW CREATE TABLE {table}")
        print(f"--- DDL for {table} ---")
        print(result)
        print("-----------------------")
    except Exception as e:
        print(f"Error fetching DDL for {table}: {e}")
