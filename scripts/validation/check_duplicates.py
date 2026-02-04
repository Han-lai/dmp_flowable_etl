import clickhouse_connect
from collections import Counter

def main():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    dates = ['2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"\n--- Analysis for {d} (WJ2 NBU E5 V3) ---")
        q = f"""
            SELECT task_id, mo_number, task_definition_key, task_name
            FROM silver.mv_fact_task_vx FINAL
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}')
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
              AND is_excluded = 0
        """
        rows = client.query(q).result_rows
        
        total_tasks = len(rows)
        distinct_mos = len(set([r[1] for r in rows]))
        
        print(f"Total Tasks: {total_tasks}")
        print(f"Distinct MOs: {distinct_mos}")
        
        # Check rare keys
        key_counts = Counter([r[2] for r in rows])
        rare_keys = [k for k, v in key_counts.items() if v <= 2]
        
        if rare_keys:
            print(f"Rare Keys (Count <= 2):")
            for r in rows:
                if r[2] in rare_keys:
                    print(f"  - Key: {r[2]}, Name: {r[3]}, MO: {r[1]}")

if __name__ == "__main__":
    main()
