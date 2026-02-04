import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def inspect_n23_done():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    # List tasks that ended on 12/27
    sql = f"""
    SELECT 
        task_id,
        task_name,
        task_start_date,
        task_end_date,
        task_status
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_end_date = '2025-12-27'
    """
    print("\n--- N23 Tasks Ended on 12/27 ---")
    print(tabulate(client.query_df(sql), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    inspect_n23_done()
