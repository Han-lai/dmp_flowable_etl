import clickhouse_connect
import pandas as pd

def check_n23_proc_ends():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    # Check unique proc_inst_id where ANY task ended on 12/27
    sql = f"""
    SELECT 
        count(DISTINCT proc_inst_id) as ended_procs
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_end_date = '2025-12-27'
    """
    print("\n--- N23 Unique Processes Ended on 12/27 ---")
    print(client.query_df(sql))

    # Also check daily for the whole week
    sql_daily = f"""
    SELECT 
        task_end_date,
        count(DISTINCT proc_inst_id) as ended_procs
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_end_date BETWEEN '2025-12-25' AND '2025-12-31'
    GROUP BY task_end_date
    ORDER BY task_end_date
    """
    print("\n--- N23 Daily Process Ends ---")
    print(client.query_df(sql_daily))

if __name__ == "__main__":
    check_n23_proc_ends()
