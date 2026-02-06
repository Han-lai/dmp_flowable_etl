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
    
    print("=== Searching for matches for W51 (Acc 29) and W52 (Acc 46) ===")
    query = """
    SELECT 
        snapshot_date,
        total_task,
        acc_todo_doing
    FROM gold.rmv_l5_task_completion FINAL
    WHERE region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5' AND vx_type='V3'
      AND snapshot_date BETWEEN '2025-12-19' AND '2025-12-31'
    ORDER BY snapshot_date
    """
    result = client.query(query)
    
    print("| Date | Day | Total | Acc | Match? |")
    print("|------|-----|-------|----:|--------|")
    import datetime
    for row in result.result_rows:
        dt = row[0]
        day_name = dt.strftime('%a')
        match = ""
        if row[2] == 29: match = "<- W51?"
        if row[2] == 46: match = "<- W52?"
        print(f"| {dt} | {day_name} | {row[1]:5d} | {row[2]:4d} | {match} |")

if __name__ == "__main__":
    main()
