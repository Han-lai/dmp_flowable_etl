#!/usr/bin/env python3
import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    target_date = '2025-12-25'
    
    print(f"=== Rolling Window Test for {target_date} ===")
    
    # Range D-6 to D: 2025-12-19 to 2025-12-25
    query_rolling = f"""
        SELECT 
            countIf(toDate('{target_date}') < task_claim_date OR (toDate('{target_date}') < task_end_date AND task_claim_date IS NULL)) as s_todo,
            countIf(toDate('{target_date}') >= task_claim_date AND (toDate('{target_date}') < task_end_date OR task_end_date IS NULL)) as s_doing
        FROM silver.mv_fact_task_vx FINAL
        WHERE (
            (task_start_date BETWEEN toDate('{target_date}') - 6 AND toDate('{target_date}'))
            OR (task_claim_date BETWEEN toDate('{target_date}') - 6 AND toDate('{target_date}'))
            OR (task_end_date BETWEEN toDate('{target_date}') - 6 AND toDate('{target_date}'))
        )
        AND (task_end_date > '{target_date}' OR task_end_date IS NULL)
        AND task_start_date <= '{target_date}'
        AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND is_excluded = 0 AND vx_type = 'V3'
    """
    todo, doing = client.query(query_rolling).result_rows[0]
    print(f"Rolling 7-Day Window (Activity within last 7 days + still pending):")
    print(f"  Todo:  {todo}")
    print(f"  Doing: {doing}")
    print(f"  Sum (Acc): {todo + doing}")

if __name__ == "__main__":
    main()
