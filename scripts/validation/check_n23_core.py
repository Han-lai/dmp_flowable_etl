import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_core_task_logic():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    # Check specific keys on 12/25
    sql_1225 = f"""
    SELECT 
        task_definition_key,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_end_date = '2025-12-25'
    GROUP BY task_definition_key
    """
    print("\n--- N23 Task Keys Ended on 12/25 (User Done: 13) ---")
    print(tabulate(client.query_df(sql_1225), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_core_task_logic()
