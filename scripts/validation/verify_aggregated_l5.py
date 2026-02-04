#!/usr/bin/env python3
import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    # Define periods: (Name, StartDate, EndDate)
    periods = [
        ("W51 (2025)", "2025-12-15", "2025-12-21"),
        ("W52 (2025)", "2025-12-22", "2025-12-28"),
        ("W01 (2026)", "2025-12-29", "2026-01-04"),
        ("Dec 2025", "2025-12-01", "2025-12-31")
    ]
    
    # Define scopes: (Plant, Factory, Line)
    scopes = [
        ("WJ2", "NBU", "E5"),
        ("WJ2", "NBU", "E4"),
        ("WJ2", "NBA", "N5")
    ]
    
    print("=== L5 Aggregated Metrics Verification ===")
    print("Logic: Activity in [Start, End], Status as of EndDate")
    print()

    for plant, factory, line in scopes:
        print(f"--- Scope: {plant} {factory} {line} (V3) ---")
        print("| Period | Total | TODO | DOING | DONE | Doing+Done | Acc |")
        print("|:---|---:|---:|---:|---:|---:|---:|")
        
        for name, start, end in periods:
            query = f"""
                SELECT 
                    count() as total,
                    -- Status as of end date
                    countIf(toDate('{end}') < task_claim_date OR (toDate('{end}') < task_end_date AND task_claim_date IS NULL)) as todo,
                    countIf(toDate('{end}') >= task_claim_date AND (toDate('{end}') < task_end_date OR task_end_date IS NULL)) as doing,
                    countIf(toDate('{end}') >= task_end_date AND task_end_date IS NULL = 0) as done
                FROM silver.mv_fact_task_vx FINAL
                WHERE (
                    (task_start_date BETWEEN '{start}' AND '{end}')
                    OR (task_claim_date BETWEEN '{start}' AND '{end}')
                    OR (task_end_date BETWEEN '{start}' AND '{end}')
                )
                AND plant = '{plant}' 
                AND factory = '{factory}' 
                AND line = '{line}'
                AND vx_type = 'V3'
                AND is_excluded = 0
            """
            result = client.query(query)
            
            if result.result_rows:
                total, todo, doing, done = result.result_rows[0]
                dd = doing + done
                acc = todo + doing
                print(f"| {name} | {total:>5} | {todo:>4} | {doing:>5} | {done:>4} | {dd:>10} | {acc:>3} |")
            else:
                print(f"| {name} |     0 |    0 |     0 |    0 |          0 |   0 |")
        print()

if __name__ == "__main__":
    main()
