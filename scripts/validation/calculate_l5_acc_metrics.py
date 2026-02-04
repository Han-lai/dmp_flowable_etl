import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def run_calculation():
    # ClickHouse connection parameters
    host = 'REDACTED_IP'
    port = 8121
    username = 'default'
    password = 'default'

    client = clickhouse_connect.get_client(host=host, port=port, username=username, password=password)

    # Define target weeks
    target_weeks = [
        {"start": "2025-12-15", "end": "2025-12-21", "label": "Week 1 (Dec 15)"},
        {"start": "2025-12-22", "end": "2025-12-28", "label": "Week 2 (Dec 22)"}
    ]

    # After MDM Fix (2026-02-04), region is now correctly mapped to CNE via MFG_SITE
    filters = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'"

    print(f"--- 篩選維度 (已修正 MDM 歸屬): {filters} ---\n")

    print("--- 1. Snapshot 指標比較 (TODO / DOING / DONE) ---")
    snapshot_queries = []
    for week in target_weeks:
        snapshot_queries.append(f"""
        SELECT 
            '{week['label']}' as week,
            sum(todo_count) as todo_count,
            sum(doing_count) as doing_count,
            sum(done_count) as done_count
        FROM gold.rmv_l5_task_completion
        WHERE snapshot_date BETWEEN '{week['start']}' AND '{week['end']}'
          AND {filters}
        """)
    
    full_snapshot_sql = " UNION ALL ".join(snapshot_queries)
    df_snapshot = client.query_df(full_snapshot_sql)
    print(tabulate(df_snapshot, headers='keys', tablefmt='psql', showindex=False))

    print("\n--- 2. ACC 指標比較 (TODO+DOING ACC) ---")
    acc_queries = []
    for week in target_weeks:
        acc_queries.append(f"""
        SELECT 
            '{week['label']}' as week,
            '{week['start']}' as p_start,
            '{week['end']}' as p_end,
            count(DISTINCT task_id) as todo_doing_acc
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0
          AND task_start_date <= '{week['end']}'
          AND (task_end_date >= '{week['start']}' OR task_end_date IS NULL)
          AND {filters}
        """)
    
    full_acc_sql = " UNION ALL ".join(acc_queries)
    df_acc = client.query_df(full_acc_sql)
    print(tabulate(df_acc, headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    run_calculation()
