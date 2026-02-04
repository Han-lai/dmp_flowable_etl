import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    keys = ['V3_5_4_1_1', 'V3_5_1_1_3', 'V3_5_3_11_1']
    keys_str = tuple(keys)
    
    print(f"\n--- Checking Keys {keys} on 12/25 (WJ2 NBU E5 V3) ---")
    q = f"""
        SELECT task_definition_key, count()
        FROM silver.mv_fact_task_vx FINAL 
        WHERE (task_start_date = '2025-12-25' OR task_claim_date = '2025-12-25' OR task_end_date = '2025-12-25') 
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
          AND vx_type = 'V3'
          AND is_excluded = 0
          AND task_definition_key IN {keys_str}
        GROUP BY task_definition_key
    """
    rows = client.query(q).result_rows
    
    if rows:
        for r in rows:
            print(f"Key: {r[0]}, Count: {r[1]}")
    else:
        print("None of these keys found on 12/25.")

if __name__ == "__main__":
    main()
