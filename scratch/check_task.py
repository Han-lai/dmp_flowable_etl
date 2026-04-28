import clickhouse_connect
import pandas as pd
import os

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', '10.146.206.76'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', '1qaz2wsx3edc'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

def check_task_status(tid):
    client = clickhouse_connect.get_client(**CH_CONFIG)
    query = f"""
    SELECT 
        task_id, 
        mo_number,
        task_start_date, 
        task_claim_date, 
        task_end_date 
    FROM silver.mv_fact_task_vx FINAL 
    WHERE task_id = '{tid}'
    """
    res = client.query(query)
    if not res.result_rows:
        print(f"Task {tid} not found.")
        return
        
    row = res.result_rows[0]
    sid, mo, start, claim, end = row
    
    # Apply V4.2 Logic
    category = "Other"
    if end == start:
        category = "Done"
    elif claim == start and end != start:
        category = "Doing"
    elif claim != start and end != start:
        category = "Todo"
        
    print(f"\n[Task Audit: {tid}]")
    print("-" * 50)
    print(f"Mo Number     : {mo}")
    print(f"Start Date    : {start}")
    print(f"Claim Date    : {claim}")
    print(f"End Date      : {end}")
    print(f"V4.2 Category : {category}")
    print(f"Snapshot Date : {start} (V4.1/V4.2 is Start-Anchored)")

if __name__ == "__main__":
    check_task_status('03b686ef-e22b-11f0-b24f-5e140ac69200')
