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
    
    print("=== Diagnostic: Raw Silver Layer Tasks ===")
    query = """
        SELECT 
            task_id,
            vx_type,
            task_status,
            task_definition_key,
            mo_number,
            task_start_date,
            task_claim_date,
            task_end_date,
            is_excluded,
            exclude_reason
        FROM silver.mv_fact_task_vx FINAL
        WHERE (task_start_date = '2025-12-25' OR task_claim_date = '2025-12-25' OR task_end_date = '2025-12-25')
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
        LIMIT 200
    """
    result = client.query(query)
    
    # Print summary
    vx_counts = {}
    status_counts = {}
    
    print(f"{'TaskID':<40} | {'Vx':<5} | {'Stat':<6} | {'DefKey':<15} | {'MO':<15} | {'Start':<10} | {'End':<10}")
    print("-" * 120)
    
    for row in result.result_rows:
        tid, vx, stat, defkey, mo, start, claim, end, excluded, reason = row
        vx_counts[vx] = vx_counts.get(vx, 0) + 1
        status_counts[stat] = status_counts.get(stat, 0) + 1
        print(f"{tid:<40} | {vx:<5} | {stat:<6} | {defkey:<15} | {mo:<15} | {str(start):<10} | {str(end):<10}")

    print("\n=== Summary ===")
    print("Vx Counts:", vx_counts)
    print("Status Counts:", status_counts)

if __name__ == "__main__":
    main()
