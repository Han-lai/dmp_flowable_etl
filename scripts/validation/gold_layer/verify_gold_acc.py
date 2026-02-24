
import os
import clickhouse_connect
import pandas as pd
from datetime import datetime

# ClickHouse connection details (User Provided)
CH_HOST = 'REDACTED_IP'
CH_PORT = 8121
CH_USER = 'default'
CH_PASSWORD = 'default'

def verify_gold_acc():
    try:
        print(f"Connecting to ClickHouse at {CH_HOST}:{CH_PORT}...")
        client = clickhouse_connect.get_client(
            host=CH_HOST,
            port=CH_PORT,
            username=CH_USER,
            password=CH_PASSWORD
        )

        query = """
        WITH 
            target_date AS (SELECT toDate('2025-12-28') as val),
            target_scope AS (
                SELECT 'CNE' as region, 'WJ2' as plant, 'NBU' as factory, 'E5' as line, 'V3' as vx_type
            ),
            raw_data AS (
                SELECT *
                FROM gold.rmv_l5_task_completion
                WHERE snapshot_date BETWEEN (SELECT val - 6 FROM target_date) AND (SELECT val FROM target_date)
                  AND region = (SELECT region FROM target_scope)
                  AND plant = (SELECT plant FROM target_scope)
                  AND factory = (SELECT factory FROM target_scope)
                  AND line = (SELECT line FROM target_scope)
                  AND vx_type = (SELECT vx_type FROM target_scope)
            )

        SELECT 
            '2025-12-28' as date,
            (SELECT total_task FROM raw_data WHERE snapshot_date = (SELECT val FROM target_date)) as daily_total_task,
            (SELECT acc_todo_doing FROM raw_data WHERE snapshot_date = (SELECT val FROM target_date)) as acc_qty,
            sum(total_task) as rolling_7d_total,
            round(
                (SELECT acc_todo_doing FROM raw_data WHERE snapshot_date = (SELECT val FROM target_date)) * 100.0 
                / nullIf(sum(total_task), 0), 
            2) as acc_rate_pct
        FROM raw_data;
        """
        
        print("Executing Query...")
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        
        print("\n=== Verification Result (Gold Layer) ===")
        print(df.to_string(index=False))
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    verify_gold_acc()
