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

try:
    client = clickhouse_connect.get_client(**CH_CONFIG)

    sql = """
    SELECT 
        line,
        bitmapCardinality(groupBitmapMergeState(total_task)) as total,
        bitmapCardinality(groupBitmapMergeState(todo_monthly)) as todo,
        bitmapCardinality(groupBitmapMergeState(doing_monthly)) as doing,
        bitmapCardinality(groupBitmapMergeState(done_monthly)) as done
    FROM gold.rmv_l5_task_completion_phys FINAL
    WHERE vx_type = 'V3'
      AND region = 'CNS'
      AND plant = 'DG3'
      AND factory = 'POT'
      AND line IN ('S21', 'S22', 'S23', 'S24', 'S25')
      AND toYYYYMM(snapshot_date) = 202512
    GROUP BY line
    ORDER BY line
    """

    print(f"Executing SQL:\n{sql}\n")
    result = client.query(sql)
    
    if result.result_rows:
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print("=== Gold Layer Aggregation (Monthly Cohort: 2025-12) ===")
        print(df.to_string(index=False))
        
        # Calculate totals across all lines
        print("\n=== Grand Total ===")
        print(f"Total: {df['total'].sum()}")
        print(f"Todo:  {df['todo'].sum()}")
        print(f"Doing: {df['doing'].sum()}")
        print(f"Done:  {df['done'].sum()}")
    else:
        print("No data found for the given criteria.")

except Exception as e:
    print(f"Error querying ClickHouse: {e}")
