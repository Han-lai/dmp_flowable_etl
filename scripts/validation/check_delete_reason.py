import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    dates = ['2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"--- Checking for non-empty DELETE_REASON_ for WJ2 NBU E5 V3 on {d} ---")
        # Step 1: Find candidate IDs in Silver (to filter by scope)
        q_ids = f"""
            SELECT task_id, task_definition_key, mo_number, vx_type
            FROM silver.mv_fact_task_vx FINAL
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}')
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
        """
        rows_mv = client.query(q_ids).result_rows
        ids = [f"'{r[0]}'" for r in rows_mv]
        
        if not ids:
            print("No tasks found in Silver for this scope/date.")
            continue
            
        # Step 2: Check their DELETE_REASON_ in Bronze
        q_bronze = f"""
            SELECT ID_, DELETE_REASON_, END_TIME_
            FROM bronze.bpm_act_hi_taskinst
            WHERE ID_ IN ({','.join(ids)})
              AND DELETE_REASON_ IS NOT NULL AND DELETE_REASON_ != ''
        """
        rows_bz = client.query(q_bronze).result_rows
        print(f"Found {len(rows_bz)} tasks with non-empty delete_reason:")
        for r in rows_bz:
            # Match back to get more info
            info = next((rm for rm in rows_mv if rm[0] == r[0]), None)
            print(f"ID: {r[0]}, Reason: {r[1]}, End: {r[2]}, Key: {info[1]}, MO: {info[2]}")

if __name__ == "__main__":
    main()
