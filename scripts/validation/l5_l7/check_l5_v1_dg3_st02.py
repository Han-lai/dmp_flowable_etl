import clickhouse_connect
import pandas as pd
from datetime import datetime, timedelta

# ClickHouse Connection Details
HOST = '10.136.218.207'
PORT = 8121
USER = 'default'
PASSWORD = 'default'

def check_l5_metrics():
    client = clickhouse_connect.get_client(host=HOST, port=PORT, username=USER, password=PASSWORD)

    query = """
    SELECT
        snapshot_date,
        vx_type,
        region,
        plant,
        factory,
        line,
        total_task,
        todo_count,
        doing_count,
        done_count,
        acc_todo_doing
    FROM gold.rmv_l5_task_completion
    WHERE vx_type = 'V1'
      AND plant = 'DG3'
      AND snapshot_date >= toDate('2025-11-01')
    ORDER BY snapshot_date
    """

    print(f"Executing Query: {query}")
    try:
        df = client.query_df(query)
        
        if df.empty:
            print("No data found for V1 in DG3")
        else:
            print(f"\nUnique Locations for V1/DG3:")
            print(df[['factory', 'line']].drop_duplicates().to_string(index=False))
            
            print("\nAggregated Counts for V1/DG3 (NPE):")
            print(f"Total Tasks: {df['total_task'].sum()}")
            print(f"Todo: {df['todo_count'].sum()}")
            print(f"Doing: {df['doing_count'].sum()}")
            print(f"Done: {df['done_count'].sum()}")
            print(f"Acc (Avg): {df['acc_todo_doing'].mean():.2f}")

    except Exception as e:
        print(f"Error executing query: {e}")

if __name__ == "__main__":
    check_l5_metrics()
