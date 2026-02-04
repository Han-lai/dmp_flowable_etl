import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_1229_keys():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    sql = f"""
    SELECT 
        task_definition_key,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_end_date = '2025-12-29'
    GROUP BY task_definition_key
    ORDER BY cnt DESC
    """
    print("\n--- N23 Task Keys Ended on 12/29 (User Done: 14) ---")
    print(tabulate(client.query_df(sql), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_1229_keys()
