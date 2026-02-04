import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_npe3_events():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    # Check NPE3 on 12/26 (User said 158)
    sql = """
    SELECT 
        count(DISTINCT task_id) as total_event,
        countIf(task_start_date = '2025-12-26') as started,
        countIf(task_end_date = '2025-12-26') as ended
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND line = 'NPE3'
      AND (task_start_date = '2025-12-26' OR task_claim_date = '2025-12-26' OR task_end_date = '2025-12-26')
    """
    print("\n--- NPE3 12/26 Event-based Count ---")
    print(client.query_df(sql))

if __name__ == "__main__":
    check_npe3_events()
