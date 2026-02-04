import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_excluded_npi():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    # Check counts of excluded tasks for Dec in N23
    sql = f"""
    SELECT 
        is_excluded,
        COALESCE(exclude_reason, 'Normal') as reason,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE {filters_n23}
      AND task_start_date BETWEEN '2025-12-01' AND '2025-12-31'
    GROUP BY is_excluded, reason
    """
    df_exc = client.query_df(sql)
    print("\n--- N23 Dec Exclusion Breakdown (MO 19/2) ---")
    print(tabulate(df_exc.fillna('None'), headers='keys', tablefmt='psql', showindex=False))

    # Daily distribution including excluded
    sql_daily = f"""
    SELECT 
        task_start_date,
        count() as total_all,
        countIf(is_excluded = 0) as total_non_excluded,
        countIf(is_excluded = 1) as total_excluded
    FROM silver.mv_fact_task_vx FINAL
    WHERE {filters_n23}
      AND task_start_date BETWEEN '2025-12-25' AND '2025-12-30'
    GROUP BY task_start_date
    ORDER BY task_start_date
    """
    df_daily = client.query_df(sql_daily)
    print("\n--- N23 Daily Inclusion Check (MO 19/2) ---")
    print(tabulate(df_daily.fillna('None'), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_excluded_npi()
