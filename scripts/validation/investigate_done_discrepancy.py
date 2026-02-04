import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    dates = ['2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"--- Investigating DONE tasks on {d} for WJ2 NBU E5 V3 ---")
        q = f"""
            SELECT task_id, task_definition_key, task_end_date, mo_number, exclude_reason, is_excluded
            FROM silver.mv_fact_task_vx FINAL 
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}') 
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
            ORDER BY task_end_date DESC
        """
        rows = client.query(q).result_rows
        print(f"Total DONE tasks found: {len(rows)}")
        # Print a few to see the content, maybe focus on ones finished exactly on the date
        for r in rows:
            # We want to see if any of these should have been excluded
            print(f"ID: {r[0]}, Key: {r[1]}, End: {r[2]}, MO: {r[3]}, ExReason: {r[4]}, IsEx: {r[5]}")

if __name__ == "__main__":
    main()
