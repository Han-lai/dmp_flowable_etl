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
    
    print("| Date | Daily Todo | Daily Doing | Rolling 7-Day Acc |")
    print("|------|------------|-------------|-------------------|")

    for d in dates:
        # Daily Activity Pending
        q_daily = f"""
            SELECT 
                countIf(toDate('{d}') < task_claim_date OR (toDate('{d}') < task_end_date AND task_claim_date IS NULL)) as s_todo,
                countIf(toDate('{d}') >= task_claim_date AND (toDate('{d}') < task_end_date OR task_end_date IS NULL)) as s_doing
            FROM silver.mv_fact_task_vx FINAL
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}')
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND is_excluded = 0 AND vx_type = 'V3'
        """
        d_todo, d_doing = client.query(q_daily).result_rows[0]
        
        # Rolling 7-Day Pending
        q_rolling = f"""
            SELECT 
                count()
            FROM silver.mv_fact_task_vx FINAL
            WHERE (
                (task_start_date BETWEEN toDate('{d}') - 6 AND toDate('{d}'))
                OR (task_claim_date BETWEEN toDate('{d}') - 6 AND toDate('{d}'))
                OR (task_end_date BETWEEN toDate('{d}') - 6 AND toDate('{d}'))
            )
            AND (task_end_date > '{d}' OR task_end_date IS NULL)
            AND task_start_date <= '{d}'
            AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND is_excluded = 0 AND vx_type = 'V3'
        """
        r_acc = client.query(q_rolling).result_rows[0][0]
        
        print(f"| {d} | {d_todo:>10} | {d_doing:>11} | {r_acc:>17} |")

if __name__ == "__main__":
    main()
