import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

print("-" * 60)
print("Schema of silver.dim_config_users")
try:
    result = client.command("DESCRIBE silver.dim_config_users")
    print(result)
except Exception as e:
    print(f"Error checking schema: {e}")
