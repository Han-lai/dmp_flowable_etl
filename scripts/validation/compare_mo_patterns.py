import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def compare_mos():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    # Check NPE3 MOs (Matched Case)
    sql_npe3 = """
    SELECT 
        substring(mo_number, 1, 5) as mo_p5,
        vx_type,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND line = 'NPE3'
      AND task_start_date BETWEEN '2025-12-01' AND '2025-12-31'
    GROUP BY mo_p5, vx_type
    """
    print("\n--- NPE3 MOs (Matched Case) ---")
    print(tabulate(client.query_df(sql_npe3), headers='keys', tablefmt='psql', showindex=False))

    # Check N23 MOs (Mismatched Case)
    sql_n23 = """
    SELECT 
        substring(mo_number, 1, 5) as mo_p5,
        vx_type,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND line = 'N23'
      AND task_start_date BETWEEN '2025-12-01' AND '2025-12-31'
    GROUP BY mo_p5, vx_type
    """
    print("\n--- N23 MOs (Mismatched Case) ---")
    print(tabulate(client.query_df(sql_n23), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    compare_mos()
