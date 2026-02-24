import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

def show_create(table):
    print(f"\n=== SHOW CREATE TABLE {table} ===")
    try:
        r = client.query(f"SHOW CREATE TABLE {table}")
        print(r.result_rows[0][0])
    except Exception as e:
        print(f"Error: {e}")

# We need to see the SELECT statement of the Materialized View
try:
    r = client.query("SHOW CREATE TABLE gold.rmv_l5_task_completion")
    ddl = r.result_rows[0][0]
    with open('gold_ddl.sql', 'w', encoding='utf-8') as f:
        f.write(ddl)
    print("DDL written to gold_ddl.sql")
except Exception as e:
    print(f"Error: {e}")
