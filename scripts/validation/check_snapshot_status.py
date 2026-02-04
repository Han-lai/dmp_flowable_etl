#!/usr/bin/env python3
import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    target_date = '2025-12-25'
    
    # Query raw data from ACT_HI_TASKINST to be sure
    query = f"""
        SELECT 
            t.ID_,
            t.TASK_DEF_KEY_,
            t.START_TIME_,
            t.CLAIM_TIME_,
            t.END_TIME_,
            v.varinst_moNumber
        FROM bronze.bpm_act_hi_taskinst t
        LEFT JOIN (
            SELECT PROC_INST_ID_, any(TEXT_) as varinst_moNumber 
            FROM bronze.bpm_act_hi_varinst 
            WHERE NAME_ = 'moNumber' 
            GROUP BY PROC_INST_ID_
        ) v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
        INNER JOIN (
            SELECT PROC_INST_ID_, any(TEXT_) as varinst_lineName 
            FROM bronze.bpm_act_hi_varinst 
            WHERE NAME_ = 'lineName' 
            GROUP BY PROC_INST_ID_
        ) vl ON t.PROC_INST_ID_ = vl.PROC_INST_ID_
        WHERE (toDate(t.START_TIME_) = '{target_date}' OR toDate(t.CLAIM_TIME_) = '{target_date}' OR toDate(t.END_TIME_) = '{target_date}')
          AND vl.varinst_lineName = 'E5'
          AND t.TASK_DEF_KEY_ NOT LIKE 'E%' AND t.TASK_DEF_KEY_ NOT LIKE 'C%'
    """
    result = client.query(query)
    
    tasks = result.result_rows
    total = len(tasks)
    
    # Analyze status AS OF end of target_date
    timestamp_limit = '2025-12-25 23:59:59'
    
    s_todo = 0
    s_doing = 0
    s_done = 0
    
    for t in tasks:
        tid, defkey, start, claim, end, mo = t
        
        # Status as of snapshot date
        # If END_TIME_ is null or > limit -> not yet done
        if end is None or str(end) > timestamp_limit:
            # If CLAIM_TIME_ is <= limit -> it was doing
            if claim is not None and str(claim) <= timestamp_limit:
                s_doing += 1
            else:
                s_todo += 1
        else:
            # End time <= limit -> done
            s_done += 1
            
    print(f"Target Date: {target_date}")
    print(f"Total Tasks: {total}")
    print(f"Status as of day end:")
    print(f"  Done:  {s_done}")
    print(f"  Doing: {s_doing}")
    print(f"  Todo:  {s_todo}")
    
    # Also check Vx based on DefKey only
    vx_v1 = sum(1 for t in tasks if str(t[1]).startswith('V1'))
    vx_v3 = sum(1 for t in tasks if str(t[1]).startswith('V3'))
    print(f"Vx classification by TaskDefKey prefix:")
    print(f"  V1: {vx_v1}")
    print(f"  V3: {vx_v3}")

if __name__ == "__main__":
    main()
