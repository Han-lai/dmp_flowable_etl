import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_date_attribution():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    # Comparison of Start Date vs Create Date
    sql = f"""
    SELECT 
        task_start_date,
        task_create_date,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND (task_start_date BETWEEN '2025-12-25' AND '2025-12-31' 
           OR task_create_date BETWEEN '2025-12-25' AND '2025-12-31')
    GROUP BY task_start_date, task_create_date
    ORDER BY task_start_date, task_create_date
    """
    print("\n--- N23 Date Attribution (Start vs Create) ---")
    print(tabulate(client.query_df(sql), headers='keys', tablefmt='psql', showindex=False))

    # Aggregated Create Date view
    sql_create = f"""
    SELECT 
        task_create_date as date_c,
        count() as total
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_create_date BETWEEN '2025-12-25' AND '2025-12-31'
    GROUP BY date_c
    ORDER BY date_c
    """
    print("\n--- N23 Daily (Based on Create Date, MO 19/2) ---")
    print(tabulate(client.query_df(sql_create), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_date_attribution()
