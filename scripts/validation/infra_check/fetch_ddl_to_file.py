
import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

tables = ['default.DMPFunctionConfig', 'default.DMPFunctionClientMapping']

with open('ddl_output.txt', 'w', encoding='utf-8') as f:
    for table in tables:
        try:
            result = client.command(f"SHOW CREATE TABLE {table}")
            f.write(f"--- DDL for {table} ---\n")
            f.write(result + "\n")
            f.write("-----------------------\n")
        except Exception as e:
            f.write(f"Error fetching DDL for {table}: {e}\n")
