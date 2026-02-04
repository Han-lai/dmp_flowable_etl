import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    dates = ['2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"\n--- Process-Task Dedup Check for {d} (WJ2 NBU E5 V3) ---")
        q = f"""
            SELECT proc_inst_id, task_definition_key
            FROM silver.mv_fact_task_vx FINAL 
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}') 
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
              AND is_excluded = 0
        """
        rows = client.query(q).result_rows
        
        total_count = len(rows)
        distinct_proc_tasks = len(set([(r[0], r[1]) for r in rows]))
        
        print(f"Total Count: {total_count}")
        print(f"Distinct (ProcID, Key) Count: {distinct_proc_tasks}")
        print(f"Difference: {total_count - distinct_proc_tasks}")

if __name__ == "__main__":
    main()
