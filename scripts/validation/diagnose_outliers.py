import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    dates = ['2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"\n--- Analyzing included DONE tasks for {d} (Silver Count vs Bronze attrs) ---")
        
        # 1. Get IDs from Silver
        q_ids = f"""
            SELECT task_id, task_definition_key
            FROM silver.mv_fact_task_vx FINAL
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}')
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
              AND is_excluded = 0
        """
        rows = client.query(q_ids).result_rows
        ids_map = {r[0]: r[1] for r in rows}
        print(f"Total tasks in Silver: {len(ids_map)}")
        
        if not ids_map:
            continue
            
        # 2. Query Bronze using IN clause (safely quoted)
        ids_list = list(ids_map.keys())
        ids_quoted = [f"'{uuid_str}'" for uuid_str in ids_list]
        ids_str = ",".join(ids_quoted)
        
        q_check = f"""
            SELECT ID_, DELETE_REASON_, PARENT_TASK_ID_, DESCRIPTION_
            FROM bronze.bpm_act_hi_taskinst
            WHERE ID_ IN ({ids_str})
              AND (
                  (DELETE_REASON_ IS NOT NULL AND DELETE_REASON_ != '') 
                  OR (PARENT_TASK_ID_ IS NOT NULL AND PARENT_TASK_ID_ != '')
                  OR (DESCRIPTION_ IS NOT NULL AND (position(lower(DESCRIPTION_), 'duplicate') > 0 OR position(lower(DESCRIPTION_), 'cancel') > 0))
              )
        """
        bronze_rows = client.query(q_check).result_rows
        
        print(f"Found {len(bronze_rows)} potential outliers:")
        for r in bronze_rows:
            print(f"  - ID: {r[0]}, Reason: {r[1]}, Parent: {r[2]}, Desc: {r[3]}, Key: {ids_map.get(r[0])}")

if __name__ == "__main__":
    main()
