import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

print("Checking table existence...")
r = client.query("SELECT name, engine FROM system.tables WHERE database='gold' AND name LIKE '%rmv_l5_task_completion%'")
print(f"Tables found: {r.result_rows}")

# Try to create a dummy table with same name to see exact error
# print("\nTrying dummy create...")
# try:
#     client.query("CREATE TABLE gold.rmv_l5_task_completion (id Int8) ENGINE=Log")
# except Exception as e:
#     print(f"Dummy create error: {e}")
