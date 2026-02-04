import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_npe3_1226():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    # Check NPE3 MOs on 12/26
    sql = """
    SELECT 
        substring(mo_number, 1, 3) as mo_p3,
        vx_type,
        count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND line = 'NPE3'
      AND task_start_date = '2025-12-26'
    GROUP BY mo_p3, vx_type
    """
    print("\n--- NPE3 MOs on 12/26 ---")
    print(tabulate(client.query_df(sql), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_npe3_1226()
