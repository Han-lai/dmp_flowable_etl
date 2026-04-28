import clickhouse_connect
import pandas as pd
import os

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', 'REDACTED_IP'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', 'REDACTED_PASSWORD'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

def query_comparison():
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    # Query V3.2 (Original)
    query_v3 = """
    SELECT 
        snapshot_date, 
        bitmapCardinality(todo) as todo_v3, 
        bitmapCardinality(doing) as doing_v3, 
        bitmapCardinality(done) as done_v3, 
        bitmapCardinality(acc) as acc_v3
    FROM gold.rmv_l5_task_completion 
    WHERE region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5' 
      AND snapshot_date BETWEEN '2025-12-25' AND '2025-12-31' 
    ORDER BY snapshot_date
    """
    
    # Query V4 (New)
    query_v4 = """
    SELECT 
        snapshot_date, 
        bitmapCardinality(todo) as todo_v4, 
        bitmapCardinality(doing) as doing_v4, 
        bitmapCardinality(done) as done_v4, 
        bitmapCardinality(acc) as acc_v4
    FROM gold.rmv_l5_task_completion_v4 
    WHERE region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5' 
      AND snapshot_date BETWEEN '2025-12-25' AND '2025-12-31' 
    ORDER BY snapshot_date
    """
    
    v3_df = pd.DataFrame(client.query(query_v3).result_rows, columns=['snapshot_date', 'todo_v3', 'doing_v3', 'done_v3', 'acc_v3'])
    v4_df = pd.DataFrame(client.query(query_v4).result_rows, columns=['snapshot_date', 'todo_v4', 'doing_v4', 'done_v4', 'acc_v4'])
    
    merged = pd.merge(v3_df, v4_df, on='snapshot_date')
    
    print("\n[Comparison: V3.2 (Snapshot/Cumulative) vs V4.0 (Activity/Rolling)]")
    print("-" * 100)
    print(merged.to_string(index=False))

if __name__ == "__main__":
    query_comparison()
