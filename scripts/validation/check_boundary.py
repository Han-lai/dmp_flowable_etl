import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    dates = ['2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"\n--- Boundary Check for {d} (WJ2 NBU E5 V3) ---")
        # Check tasks ending near 00:00:00 or 23:59:59
        # ClickHouse stores DateTime?
        q = f"""
            SELECT task_id, task_end_date, toHour(task_end_date), toMinute(task_end_date), toSecond(task_end_date)
            FROM silver.mv_fact_task_vx FINAL 
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}') 
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
              AND is_excluded = 0
              AND ((toHour(task_end_date) = 23 AND toMinute(task_end_date) >= 50) OR (toHour(task_end_date) = 0 AND toMinute(task_end_date) <= 10))
            ORDER BY task_end_date
        """
        rows = client.query(q).result_rows
        
        print(f"Tasks near boundary: {len(rows)}")
        for r in rows:
            print(f"  - ID: {r[0]}, End: {r[1]}")

if __name__ == "__main__":
    main()
