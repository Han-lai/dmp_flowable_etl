import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_n23_raw():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    filters_n23 = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23'"
    
    # List Task Keys in N23 (Dec)
    sql_keys = f"""
    SELECT 
        task_definition_key,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_start_date BETWEEN '2025-12-01' AND '2025-12-31'
    GROUP BY task_definition_key
    ORDER BY cnt DESC
    LIMIT 20
    """
    print("\n--- N23 Task Keys (Dec) ---")
    print(tabulate(client.query_df(sql_keys), headers='keys', tablefmt='psql', showindex=False))

    # List MO Patterns in N23 (Dec)
    sql_mos = f"""
    SELECT 
        substring(mo_number, 1, 5) as mo_p5,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_start_date BETWEEN '2025-12-01' AND '2025-12-31'
    GROUP BY mo_p5
    ORDER BY cnt DESC
    """
    print("\n--- N23 MO Prefix (5 chars) ---")
    print(tabulate(client.query_df(sql_mos), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_n23_raw()
