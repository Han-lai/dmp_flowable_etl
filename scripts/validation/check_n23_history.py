import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_n23_history():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    dates = ['2025-12-25', '2025-12-26', '2025-12-31']
    
    for d in dates:
        print(f"\n{'='*20} Date: {d} {'='*20}")
        # Total with MO filter (Excluding 315)
        sql_mo = f"""
        SELECT 
            substring(mo_number, 1, 3) as mo_p3,
            count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 AND line = 'N23'
          AND task_start_date = '{d}'
          AND mo_number NOT LIKE '315%'
        GROUP BY mo_p3
        """
        print(f"--- MO-based (Excluding 315) on {d} ---")
        print(tabulate(client.query_df(sql_mo), headers='keys', tablefmt='psql', showindex=False))

        # Total with Key filter (Starts with V1)
        sql_key = f"""
        SELECT 
            count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 AND line = 'N23'
          AND task_start_date = '{d}'
          AND task_definition_key LIKE 'V1%'
        """
        print(f"--- Key-based (V1%) on {d} ---")
        print(client.query_df(sql_key).iloc[0,0])

if __name__ == "__main__":
    check_n23_history()
