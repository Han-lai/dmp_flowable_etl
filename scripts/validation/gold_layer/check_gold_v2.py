import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

try:
    print("Querying View V2...")
    r = client.query("SELECT count() FROM gold.rmv_l5_task_completion_v2")
    print(f"View Count: {r.result_rows[0][0]}")
    
    # Check specific data
    r2 = client.query("SELECT count() FROM gold.rmv_l5_task_completion_v2 WHERE plant='DG3' AND factory='SMT' AND line='ST02'")
    print(f"DG3/SMT/ST02 Count: {r2.result_rows[0][0]}")
    
except Exception as e:
    print(f"Error: {e}")
