import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

try:
    print("Checking View Definition...")
    r = client.query("SHOW CREATE TABLE gold.rmv_l5_task_completion")
    print(r.result_rows[0][0])
    
    print("\nQuerying View...")
    r = client.query("SELECT count() FROM gold.rmv_l5_task_completion")
    print(f"View Count: {r.result_rows[0][0]}")
    
except Exception as e:
    print(f"Error: {e}")
