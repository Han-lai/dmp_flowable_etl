import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def locate_n23_ended():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    # Broad search for N23 ended on 12/27
    sql = """
    SELECT 
        region, plant, factory, line, vx_type, is_excluded, count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE line = 'N23' AND (mo_number LIKE '19%' OR mo_number LIKE '2%')
      AND task_end_date = '2025-12-27'
    GROUP BY region, plant, factory, line, vx_type, is_excluded
    """
    print("\n--- N23 Tasks Ended on 12/27 Location ---")
    print(tabulate(client.query_df(sql), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    locate_n23_ended()
