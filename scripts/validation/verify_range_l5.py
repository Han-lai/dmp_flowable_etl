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
    
    dates = ['2025-12-25', '2025-12-26', '2025-12-27', '2025-12-28', '2025-12-29', '2025-12-30', '2025-12-31']
    
    print("=== L5 Indicators Range Verification (WJ2 NBU E5) ===")
    print("Calculated from Silver Layer (Point-in-time status)")
    print()
    print("| Date | Vx | Total | TODO | DOING | DONE | Doing+Done | Todo+Doing(Acc) |")
    print("|------|----|------:|-----:|------:|-----:|-----------:|----------------:|")

    for d in dates:
        # Daily Activity Population
        # But Acc needs to look at tasks with activity in [D-6, D]
        query = f"""
            SELECT 
                vx_type,
                -- 1. Total Daily Tasks (Activity on D)
                countIf(task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}') as total,
                
                -- 2. Daily Todo/Doing (Activity on D AND pending on D)
                countIf((task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}') AND (toDate('{d}') < task_claim_date OR (toDate('{d}') < task_end_date AND task_claim_date IS NULL))) as todo,
                countIf((task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}') AND (toDate('{d}') >= task_claim_date AND (toDate('{d}') < task_end_date OR task_end_date IS NULL))) as doing,
                countIf((task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}') AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)) as done,
                
                -- 3. Acc (Activity in [D-6, D] AND pending on D)
                countIf(
                    (
                        (task_start_date BETWEEN toDate('{d}') - 6 AND toDate('{d}'))
                        OR (task_claim_date BETWEEN toDate('{d}') - 6 AND toDate('{d}'))
                        OR (task_end_date BETWEEN toDate('{d}') - 6 AND toDate('{d}'))
                    )
                    AND (task_end_date > '{d}' OR task_end_date IS NULL)
                    AND task_start_date <= '{d}'
                ) as acc
            FROM silver.mv_fact_task_vx FINAL
            WHERE plant = 'WJ2' 
              AND factory = 'NBU' 
              AND line = 'E5'
              AND is_excluded = 0
            GROUP BY vx_type
            HAVING total > 0 OR acc > 0
            ORDER BY vx_type
        """
        result = client.query(query)
        
        for row in result.result_rows:
            vx, total, todo, doing, done, acc = row
            dd = doing + done
            print(f"| {d} | {vx} | {total:>5} | {todo:>4} | {doing:>5} | {done:>4} | {dd:>10} | {acc:>15} |")

if __name__ == "__main__":
    main()
