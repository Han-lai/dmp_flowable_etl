import clickhouse_connect
import pandas as pd
import os

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', '10.146.206.76'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', '1qaz2wsx3edc'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

def query_v4_results():
    client = clickhouse_connect.get_client(**CH_CONFIG)
    query = """
    SELECT 
        snapshot_date, 
        bitmapCardinality(todo) as todo, 
        bitmapCardinality(doing) as doing, 
        bitmapCardinality(done) as done, 
        bitmapCardinality(acc) as acc_wip
    FROM gold.rmv_l5_task_completion_v4 
    WHERE region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5' 
      AND snapshot_date BETWEEN '2025-12-25' AND '2025-12-31' 
    ORDER BY snapshot_date
    """
    res = client.query(query)
    df = pd.DataFrame(res.result_rows, columns=res.column_names)
    print("\n[V4 Activity Mode - CNE WJ2 NBU E5 (Dec 25-31)]")
    print(df.to_string(index=False))

if __name__ == "__main__":
    query_v4_results()
