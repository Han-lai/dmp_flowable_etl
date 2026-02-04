import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    dates = ['2025-12-25', '2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"\n--- Checking V3_5_4% Keys on {d} (WJ2 NBU E5 V3) ---")
        q = f"""
            SELECT task_definition_key, task_name, count()
            FROM silver.mv_fact_task_vx FINAL 
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}') 
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND is_excluded = 0
              AND task_definition_key LIKE 'V3_5_4%'
            GROUP BY task_definition_key, task_name
        """
        rows = client.query(q).result_rows
        
        if rows:
            for r in rows:
                print(f"Key: {r[0]}, Name: {r[1]}, Count: {r[2]}")
        else:
            print("No V3_5_4% keys found.")

if __name__ == "__main__":
    main()
