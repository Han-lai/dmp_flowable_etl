import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    dates = ['2025-12-30', '2025-12-31']
    
    for d in dates:
        print(f"\n--- Process Deletion Check for {d} (WJ2 NBU E5 V3) ---")
        
        # 1. Get Task and Proc IDs from Silver
        q_ids = f"""
            SELECT task_id, proc_inst_id
            FROM silver.mv_fact_task_vx FINAL
            WHERE (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}')
              AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
              AND vx_type = 'V3'
              AND (toDate('{d}') >= task_end_date AND task_end_date IS NULL = 0)
              AND is_excluded = 0
        """
        rows = client.query(q_ids).result_rows
        proc_map = {r[1]: r[0] for r in rows} # ProcID -> TaskID (just one sample task per proc is enough to flag)
        
        print(f"Total Tasks: {len(rows)}")
        print(f"Distinct Process IDs: {len(proc_map)}")
        
        if not proc_map:
            continue
            
        # 2. Query Bronze Process Instance table
        procs_list = list(proc_map.keys())
        procs_quoted = [f"'{pid}'" for pid in procs_list]
        procs_str = ",".join(procs_quoted)
        
        q_check = f"""
            SELECT ID_, DELETE_REASON_
            FROM bronze.bpm_act_hi_procinst
            WHERE ID_ IN ({procs_str})
              AND DELETE_REASON_ IS NOT NULL AND DELETE_REASON_ != ''
        """
        
        # Note: I need to be sure bpm_act_hi_procinst exists and has DELETE_REASON_
        # I'll Assume it follows the standard Flowable schema, same as taskinst
        
        try:
            deleted_procs = client.query(q_check).result_rows
            print(f"Found {len(deleted_procs)} Deleted Process Instances:")
            for p in deleted_procs:
                print(f"  - ProcID: {p[0]}, Reason: {p[1]}")
                # Count how many tasks belong to this proc
                related_tasks = [r[0] for r in rows if r[1] == p[0]]
                print(f"    -> Affects {len(related_tasks)} tasks")
                
        except Exception as e:
            print(f"Query failed: {e}")

if __name__ == "__main__":
    main()
