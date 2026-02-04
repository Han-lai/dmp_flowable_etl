import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def analyze_n23_discrepancy():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    filters_n23 = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23'"
    
    # 1. Total Started in Dec by Vx Type and Task Key Prefix
    # Check if a specific combination matches ~275
    sql_total = f"""
    SELECT 
        vx_type,
        substring(task_definition_key, 1, 2) as key_prefix,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_start_date BETWEEN '2025-12-01' AND '2025-12-31'
    GROUP BY vx_type, key_prefix
    ORDER BY cnt DESC
    """
    print("\n--- N23 Dec Total Breakdown (Started Today) ---")
    print(tabulate(client.query_df(sql_total), headers='keys', tablefmt='psql', showindex=False))

    # 2. Check MO prefixes for the V1 tasks
    # Maybe only certain MOs are V1?
    sql_mo = f"""
    SELECT 
        substring(mo_number, 1, 3) as mo_prefix,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23} AND vx_type = 'V1'
      AND task_start_date BETWEEN '2025-12-01' AND '2025-12-31'
    GROUP BY mo_prefix
    ORDER BY cnt DESC
    """
    print("\n--- N23 Dec V1 MO Prefix Breakdown ---")
    print(tabulate(client.query_df(sql_mo), headers='keys', tablefmt='psql', showindex=False))

    # 3. List specific days for Key-based V1 (Key starts with V1)
    # User's Dec Total is 275. Let's see if Key-based matches.
    sql_key_v1 = f"""
    SELECT 
        task_start_date,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_definition_key LIKE 'V1%'
      AND task_start_date BETWEEN '2025-12-01' AND '2025-12-31'
    GROUP BY task_start_date
    ORDER BY task_start_date
    """
    print("\n--- N23 Dec Key-based V1 (Task Key Starts with V1) ---")
    df_key_v1 = client.query_df(sql_key_v1)
    print(tabulate(df_key_v1, headers='keys', tablefmt='psql', showindex=False))
    print("Total Key-based V1:", df_key_v1['cnt'].sum())

if __name__ == "__main__":
    analyze_n23_discrepancy()
