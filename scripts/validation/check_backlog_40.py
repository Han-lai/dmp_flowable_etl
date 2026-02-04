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
    
    print(f"=== Backlog Diagnostic for {target_date} (WJ2 NBU E5) ===")
    
    # 1. Tasks with ANY activity on target_date (Current Gold logic population)
    query_activity = f"""
        SELECT count() 
        FROM silver.mv_fact_task_vx FINAL
        WHERE (task_start_date = '{target_date}' OR task_claim_date = '{target_date}' OR task_end_date = '{target_date}')
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND is_excluded = 0 AND vx_type = 'V3'
    """
    activity_count = client.query(query_activity).result_rows[0][0]
    print(f"Tasks with activity on {target_date}: {activity_count}")

    # 2. Status of those activity tasks as of day end
    query_activity_status = f"""
        SELECT 
            countIf(toDate('{target_date}') < task_claim_date OR (toDate('{target_date}') < task_end_date AND task_claim_date IS NULL)) as s_todo,
            countIf(toDate('{target_date}') >= task_claim_date AND (toDate('{target_date}') < task_end_date OR task_end_date IS NULL)) as s_doing
        FROM silver.mv_fact_task_vx FINAL
        WHERE (task_start_date = '{target_date}' OR task_claim_date = '{target_date}' OR task_end_date = '{target_date}')
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND is_excluded = 0 AND vx_type = 'V3'
    """
    act_todo, act_doing = client.query(query_activity_status).result_rows[0]
    print(f"  Activity-based Todo:  {act_todo}")
    print(f"  Activity-based Doing: {act_doing}")
    print(f"  Activity-based Sum:   {act_todo + act_doing}")

    # 3. True Backlog (Stock): All tasks started <= target_date AND (not yet ended or ended > target_date)
    query_stock = f"""
        SELECT 
            countIf(toDate('{target_date}') < task_claim_date OR (toDate('{target_date}') < task_end_date AND task_claim_date IS NULL)) as s_todo,
            countIf(toDate('{target_date}') >= task_claim_date AND (toDate('{target_date}') < task_end_date OR task_end_date IS NULL)) as s_doing
        FROM silver.mv_fact_task_vx FINAL
        WHERE task_start_date <= '{target_date}'
          AND (task_end_date > '{target_date}' OR task_end_date IS NULL)
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND is_excluded = 0 AND vx_type = 'V3'
    """
    stock_todo, stock_doing = client.query(query_stock).result_rows[0]
    print(f"True Stock (All pending as of {target_date}):")
    print(f"  Stock Todo:  {stock_todo}")
    print(f"  Stock Doing: {stock_doing}")
    print(f"  Stock Sum (Acc): {stock_todo + stock_doing}")

if __name__ == "__main__":
    main()
