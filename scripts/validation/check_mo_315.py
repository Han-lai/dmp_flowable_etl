import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_mo_315():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    # Check Process Definition Keys for MO 315 in N23
    sql = """
    SELECT 
        substring(mo_number, 1, 3) as mo_p3,
        proc_inst_id,
        count() as task_cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE line = 'N23' AND mo_number LIKE '315%'
    GROUP BY mo_p3, proc_inst_id
    LIMIT 5
    """
    df = client.query_df(sql)
    if not df.empty:
        # Get one of the proc_inst_ids to check its definition
        proc_id = df.iloc[0]['proc_inst_id']
        sql_proc = f"""
        SELECT 
            p.KEY_ as process_key,
            p.NAME_ as process_name
        FROM bronze.bpm_act_hi_procinst h
        JOIN bronze.bpm_act_re_procdef p ON h.PROC_DEF_ID_ = p.ID_
        WHERE h.ID_ = '{proc_id}'
        """
        print("\n--- Process Definition for MO 315 Task ---")
        print(client.query_df(sql_proc))

if __name__ == "__main__":
    check_mo_315()
