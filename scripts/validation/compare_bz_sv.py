import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='10.136.218.107', port=8123, username='default', password='default') # Wait, host might be different in my context, let me check previous successful calls
    # Re-checking host from previous tools: REDACTED_IP:8121
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    dates = ['2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"\n--- Discrepancy Analysis for {d} (WJ2 NBU E5 V3) ---")
        
        # Silver Count
        q_silver = f"""
            SELECT count()
            FROM silver.mv_fact_task_vx FINAL 
            WHERE (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
              AND (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}')
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND is_excluded = 0
        """
        silver_count = client.query(q_silver).result_rows[0][0]
        print(f"Silver DONE Count: {silver_count}")
        
        # Bronze equivalent (need to apply the same filters)
        # Filters: is_excluded = 0 (E%, C% Key, bypass, Q/R order)
        # Scope: WJ2 NBU E5 (From MDM or Varinst)
        # Vx: V3 (From TaskDefKey or moNumber)
        
        # This is complex to do purely in Bronze because scope/vx are derived in Silver.
        # So I will list the Silver IDs and see if any of them look suspicious.
        
        q_details = f"""
            SELECT task_id, task_definition_key, mo_number, task_end_date, assignee_name
            FROM silver.mv_fact_task_vx FINAL 
            WHERE (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
              AND (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}')
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND is_excluded = 0
            ORDER BY task_end_date DESC
        """
        rows = client.query(q_details).result_rows
        # I'll print the last 10 tasks specifically to see if any are boundary cases
        print("Last 10 DONE tasks (by end date):")
        for r in rows[:10]:
            print(f"ID: {r[0]}, Key: {r[1]}, MO: {r[2]}, End: {r[3]}, Name: {r[4]}")

if __name__ == "__main__":
    main()
