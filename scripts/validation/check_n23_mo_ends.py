import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_mo_ends():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    # Check Daily Unique MOs that ended ANY task
    sql = f"""
    SELECT 
        task_end_date,
        count(DISTINCT mo_number) as ended_mos
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_end_date BETWEEN '2025-12-25' AND '2025-12-31'
    GROUP BY task_end_date
    ORDER BY task_end_date
    """
    print("\n--- N23 Daily Unique MOs with End Events ---")
    print(tabulate(client.query_df(sql), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_mo_ends()
