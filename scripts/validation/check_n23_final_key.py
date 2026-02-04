import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_final_task():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    # Check daily counts where V3_5_3_10_1 ended
    sql = f"""
    SELECT 
        task_end_date,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_definition_key = 'V3_5_3_10_1'
      AND task_end_date BETWEEN '2025-12-25' AND '2025-12-31'
    GROUP BY task_end_date
    ORDER BY task_end_date
    """
    print("\n--- N23 'V3_5_3_10_1' Ends ---")
    print(tabulate(client.query_df(sql), headers='keys', tablefmt='psql', showindex=False))

    # Also check if there's any other "final" looking key
    sql_tail = f"""
    SELECT 
        task_definition_key,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_end_date = '2025-12-27'
    GROUP BY task_definition_key
    """
    print("\n--- N23 Task Keys Ended on 12/27 ---")
    print(tabulate(client.query_df(sql_tail), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_final_task()
