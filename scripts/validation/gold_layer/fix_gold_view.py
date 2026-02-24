import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

try:
    print("Detaching View...")
    client.query("DETACH TABLE gold.rmv_l5_task_completion")
    print("Attaching View...")
    client.query("ATTACH TABLE gold.rmv_l5_task_completion")
    print("View re-attached.")
    
    print("Verifying View Query...")
    r = client.query("SELECT count() FROM gold.rmv_l5_task_completion")
    print(f"View Count: {r.result_rows[0][0]}")

except Exception as e:
    print(f"Error: {e}")
