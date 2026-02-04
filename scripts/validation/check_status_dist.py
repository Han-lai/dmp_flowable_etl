import clickhouse_connect
from collections import Counter

def main():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    dates = ['2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"\n--- Task Status Distribution for DONE tasks on {d} (WJ2 NBU E5 V3) ---")
        q = f"""
            SELECT task_status, count()
            FROM silver.mv_fact_task_vx FINAL 
            WHERE (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
              AND (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}')
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND is_excluded = 0
            GROUP BY task_status
        """
        rows = client.query(q).result_rows
        for status, count in rows:
            print(f"Status: {status}, Count: {count}")

if __name__ == "__main__":
    main()
