import clickhouse_connect
import os

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

OLD_INNER = ".inner_id.c2ede193-b8b8-426f-80ef-805b76368138"

def recover():
    print("Starting Gold View Recovery...")
    
    # 1. Drop old inner table (cleanup)
    try:
        print(f"Dropping old inner table {OLD_INNER}...")
        client.query(f"DROP TABLE IF EXISTS gold.`{OLD_INNER}`")
        print("Old inner table dropped.")
    except Exception as e:
        print(f"Error dropping inner: {e}")

    # 2. Recreate MV
    try:
        print("Recreating Materialized View...")
        with open('gold_ddl.sql', 'r', encoding='utf-8') as f:
            ddl = f.read()
            
        # Ensure we have the setting enabled just in case
        client.query("SET allow_experimental_refreshable_materialized_view=1")
        client.query(ddl)
        print("Materialized View recreated successfully.")
        
    except Exception as e:
        print(f"Error creating MV: {e}")
        # If it says exists, maybe I need to DROP (detached)?
        # Detached table shouldn't block create?
        # If it blocks, I might need to remove metadata file? (Can't do that).
        # Usually CREATE replaces if not exists?
        
    # 3. Check View
    try:
        r = client.query("SELECT count() FROM gold.rmv_l5_task_completion")
        print(f"View is accessible. Rows (should be 0 or small): {r.result_rows[0][0]}")
    except Exception as e:
        print(f"View check failed: {e}")

if __name__ == "__main__":
    recover()
