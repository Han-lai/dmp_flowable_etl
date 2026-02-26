import clickhouse_connect
import pandas as pd

def check_dg3():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    query = """
    SELECT 
        snapshot_date,
        vx_type,
        total_task,
        todo_count,
        doing_count,
        done_count,
        acc_todo_doing
    FROM gold.rmv_l5_task_completion_v2
    WHERE plant = 'DG3' 
      AND factory = 'SMT' 
      AND line = 'ST02'
      AND snapshot_date >= '2025-12-25' 
      AND snapshot_date <= '2025-12-31'
    ORDER BY snapshot_date DESC, vx_type ASC
    """
    
    result = client.query(query)
    
    if not result.result_rows:
        print("No data found for DG3/SMT/ST02 in the specified date range.")
        return

    df = pd.DataFrame(result.result_rows, columns=result.column_names)
    print("=== DG3/SMT/ST02 Task Completion Metrics (ClickHouse) ===")
    print(df.to_string(index=False))

if __name__ == "__main__":
    check_dg3()
