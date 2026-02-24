import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

def show_create(table):
    print(f"\n=== SHOW CREATE TABLE {table} ===")
    try:
        r = client.query(f"SHOW CREATE TABLE {table}")
        print(r.result_rows[0][0])
    except Exception as e:
        print(f"Error: {e}")

show_create('silver.mv_fact_task_vx')
show_create('gold.rmv_l5_task_completion')
