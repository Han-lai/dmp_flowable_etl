import clickhouse_connect
from collections import Counter

def main():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    dates = ['2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"\n===== Inspecting DONE tasks for {d} (WJ2 NBU E5 V3) =====")
        q = f"""
            SELECT mo_number, task_definition_key, substring(mo_number, 1, 3) as prefix, task_id
            FROM silver.mv_fact_task_vx FINAL 
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}') 
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
              AND is_excluded = 0
        """
        rows = client.query(q).result_rows
        print(f"Total DONE: {len(rows)}")
        
        prefixes = Counter([r[2] for r in rows])
        print("MO Prefixes:", dict(prefixes))
        
        keys = Counter([r[1] for r in rows])
        # Print top 10 keys
        print("Top 10 Task Keys:", dict(keys.most_common(10)))
        
        # Check for any "suspicious" MO numbers
        # Typically V3 MO numbers are like 315...
        suspicious = [r for r in rows if not r[0].startswith('315') and not r[0].startswith('316') and not r[0].startswith('323')]
        if suspicious:
            print(f"Found {len(suspicious)} suspicious MO numbers:")
            for s in suspicious:
                print(f"ID: {s[3]}, MO: {s[0]}, Key: {s[1]}")
        else:
            print("No suspicious MO prefixes found (all 315/316/323).")

if __name__ == "__main__":
    main()
