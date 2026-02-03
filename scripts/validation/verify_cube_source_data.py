import clickhouse_connect
import pandas as pd

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("Connecting to ClickHouse...")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("\nVerifying Cube.js Source Data (Gold Layer)")
    print("Target Table: gold.rmv_l5_task_completion (Source for cube_l5_task_completion.js)")
    print("Filter: Date=2025-12-25, Plant=WJ2, Factory=NBU, Line=E4/E5")
    
    # query_sql specific to what Cube.js would effectively run
    query = """
    SELECT
        plant,
        factory,
        line,
        sum(total_task) as TotalTask,
        sum(todo_count) as Todo,
        sum(doing_count) as Doing,
        sum(done_count) as Done,
        round(sum(done_count) * 100.0 / sum(total_task), 2) as CompletionRate
    FROM gold.rmv_l5_task_completion
    WHERE snapshot_date = '2025-12-25'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line IN ('E4', 'E5')
    GROUP BY plant, factory, line
    ORDER BY line
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        
        print("\nQuery Result:")
        print(df.to_string(index=False))
        
        print("\nVerification Criteria:")
        print("- E4 Expected: ~163 (Validated from Bronze _0108)")
        print("- E5 Expected: ~196 (Validated from Bronze _0108)")
        
        # Check logic
        e4_row = df[df['line'] == 'E4']
        e5_row = df[df['line'] == 'E5']
        
        if not e4_row.empty and not e5_row.empty:
            e4_count = e4_row.iloc[0]['TotalTask']
            e5_count = e5_row.iloc[0]['TotalTask']
            
            print(f"\nStatus Check:")
            print(f"E4 Count: {e4_count} vs 163 -> {'MATCH' if abs(e4_count - 163) < 5 else 'MISMATCH'}")
            print(f"E5 Count: {e5_count} vs 196 -> {'MATCH' if abs(e5_count - 196) < 5 else 'MISMATCH'}")
        else:
            print("\nWARNING: No data found for E4 or E5. The RMV might need refreshing.")
            
    except Exception as e:
        print(f"Query failed: {e}")

if __name__ == "__main__":
    main()
