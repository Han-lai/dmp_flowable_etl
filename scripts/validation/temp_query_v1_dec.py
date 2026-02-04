import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def run_query():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    # 1. Narrow V1 Launched in Dec by Line (for whole WJ2)
    line_v1_sql = """
    SELECT 
        factory, line,
        count() as total,
        countIf(task_status = 'DONE') as done,
        countIf(task_status IN ('TODO', 'DOING')) as unfinished
    FROM (
        SELECT factory, line, task_id,
               argMax(task_status, multiIf(task_status='DONE', 3, task_status='DOING', 2, 1)) as task_status
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 
          AND region = 'CNE' AND plant = 'WJ2'
          AND task_definition_key LIKE 'V1%'
          AND (task_start_date BETWEEN '2025-12-01' AND '2025-12-31' 
               OR task_claim_date BETWEEN '2025-12-01' AND '2025-12-31' 
               OR task_end_date BETWEEN '2025-12-01' AND '2025-12-31')
        GROUP BY factory, line, task_id
    )
    GROUP BY factory, line
    ORDER BY total DESC
    """
    print("\n--- Narrow V1 Line-level Profiling ---")
    print(tabulate(client.query_df(line_v1_sql), headers='keys', tablefmt='psql', showindex=False))

    # 2. Narrow V1 Inventory (Acc) by Line as of 12/31
    line_acc_sql = """
    SELECT 
        line,
        count() as acc
    FROM (
        SELECT line, task_id
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 
          AND region = 'CNE' AND plant = 'WJ2'
          AND task_definition_key LIKE 'V1%'
          AND task_start_date <= '2025-12-31'
          AND (task_end_date IS NULL OR task_end_date > '2025-12-31')
        GROUP BY line, task_id
    )
    GROUP BY line
    ORDER BY acc DESC
    """
    print("\n--- Narrow V1 Line-level Inventory (Acc) ---")
    print(tabulate(client.query_df(line_acc_sql), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    run_query()
