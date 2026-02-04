import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    # 1. Get stats for all 3 dates
    dates = ['2025-12-25', '2025-12-30', '2025-12-31']
    stats = {} 
    
    for d in dates:
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
            
    # Pattern B: 0 on 12/25, but present on 12/30 OR 12/31
    print(f"\n--- Candidates present on 30/31 but NOT on 25 ---")
    for key, data in stats.items():
        c25 = data['counts'].get('2025-12-25', 0)
        c30 = data['counts'].get('2025-12-30', 0)
        c31 = data['counts'].get('2025-12-31', 0)
        
        if c25 == 0 and (c30 > 0 or c31 > 0):
             print(f"Key: {key}, On25: {c25}, On30: {c30}, On31: {c31} | Name: {data['name']}")

if __name__ == "__main__":
    main()
