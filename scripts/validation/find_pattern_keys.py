import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    # 1. Get stats for all 3 dates
    dates = ['2025-12-25', '2025-12-30', '2025-12-31']
    stats = {} # Key -> {Date -> Count}
    
    for d in dates:
        print(f"Fetching stats for {d}...")
        q = f"""
            SELECT task_definition_key, task_name, count()
            FROM silver.mv_fact_task_vx FINAL 
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}') 
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
              AND is_excluded = 0
            GROUP BY task_definition_key, task_name
        """
        rows = client.query(q).result_rows
        for r in rows:
            key = r[0]
            name = r[1]
            count = r[2]
            if key not in stats:
                stats[key] = {'name': name, 'counts': {}}
            stats[key]['counts'][d] = count
            
    # 2. Filter for the pattern
    # Pattern A: 2 on 12/30, 1 on 12/31, 0 on 12/25
    candidates_a = []
    
    for key, data in stats.items():
        c25 = data['counts'].get('2025-12-25', 0)
        c30 = data['counts'].get('2025-12-30', 0)
        c31 = data['counts'].get('2025-12-31', 0)
        
        if c25 == 0 and c30 == 2 and c31 == 1:
            candidates_a.append((key, data['name']))
            
    print(f"\n--- Candidates matching Pattern (0 on 25th, 2 on 30th, 1 on 31st) ---")
    for c in candidates_a:
        print(f"Key: {c[0]}, Name: {c[1]}")

if __name__ == "__main__":
    main()
