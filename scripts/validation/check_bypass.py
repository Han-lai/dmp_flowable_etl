import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    dates = ['2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"\n--- Bypass Check for {d} (WJ2 NBU E5 V3) ---")
        
        # 1. Get Tasks
        q_ids = f"""
            SELECT task_id, proc_inst_id, task_definition_key
            FROM silver.mv_fact_task_vx FINAL
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}')
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
              AND is_excluded = 0
        """
        rows = client.query(q_ids).result_rows
        proc_keys = { (r[1], r[2]): r[0] for r in rows } # (ProcID, Key) -> TaskID
        
        print(f"Total Tasks: {len(rows)}")
        
        if not proc_keys:
            continue
            
        # 2. Query Vars
        procs = list(set([r[1] for r in rows]))
        procs_quoted = [f"'{p}'" for p in procs]
        
        # Batch query if too many? 200 is fine.
        q_vars = f"""
            SELECT PROC_INST_ID_, TEXT_, LONG_
            FROM bronze.bpm_act_hi_varinst
            WHERE NAME_ = 'taskBypass'
              AND PROC_INST_ID_ IN ({",".join(procs_quoted)})
        """
        vars_rows = client.query(q_vars).result_rows
        
        print(f"Found {len(vars_rows)} bypass variables for these processes.")
        
        # 3. Match
        found_missed_bypass = 0
        for v in vars_rows:
            proc_id = v[0]
            key = v[1]
            val = v[2]
            
            if (proc_id, key) in proc_keys:
                # We have a task with this Proc and Key.
                # Since we filtered `is_excluded=0` in Silver, and we found a bypass var here...
                # This implies the Silver join FAILED or Logic FAILED.
                # Silver logic: left join ... check tb.LONG_ = 1.
                if val == 1:
                    print(f"MISSED BYPASS! Task: {proc_keys[(proc_id, key)]}, Proc: {proc_id}, Key: {key}")
                    found_missed_bypass += 1
                else:
                    # Value is not 1?
                    print(f"Bypass var found but value is {val} for Task: {proc_keys[(proc_id, key)]}")

        if found_missed_bypass == 0:
            print("No missed bypass variables found.")

if __name__ == "__main__":
    main()
