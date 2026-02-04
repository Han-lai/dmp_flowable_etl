import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def inspect_n23_1227_details():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    # Details of the 9 tasks that ended on 12/27
    sql = f"""
    SELECT 
        task_id,
        task_name,
        task_definition_key,
        task_start_date,
        task_end_date,
        COALESCE(exclude_reason, 'None') as reason
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_end_date = '2025-12-27'
    """
    df = client.query_df(sql)
    print("\n--- Details of N23 Tasks Ended on 12/27 ---")
    print(tabulate(df, headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    inspect_n23_1227_details()
