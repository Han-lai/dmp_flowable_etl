import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    d = '2025-12-30'
    keys = ['V3_5_4_1_3', 'V3_5_4_1_2', 'V3_5_4_1_5']
    keys_str = tuple(keys)
    
    print(f"\n--- DONE Count for Recycle Keys on {d} (WJ2 NBU E5 V3) ---")
    q = f"""
        SELECT task_definition_key, count()
        FROM silver.mv_fact_task_vx FINAL 
        WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}') 
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
          AND vx_type = 'V3'
          AND is_excluded = 0
          AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0) -- DONE logic
          AND task_definition_key IN {keys_str}
        GROUP BY task_definition_key
    """
    rows = client.query(q).result_rows
    
    for r in rows:
        print(f"Key: {r[0]}, DONE Count: {r[1]}")

if __name__ == "__main__":
    main()
