import clickhouse_connect
import os

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', 'REDACTED_IP'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', 'REDACTED_PASSWORD'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

print(f"Connecting to {CH_CONFIG['host']}...")
client = clickhouse_connect.get_client(**CH_CONFIG)
print("Connected.")
query = "SELECT status, count() FROM gold.kpi_task_completion WHERE snapshot_date = '2025-11-24' GROUP BY status"
print(f"Running query: {query}")
res = client.query(query)
print("Gold data for 2025-11-24:")
if not res.result_rows:
    print("No data found in Gold for this date.")
for row in res.result_rows:
    print(row)

