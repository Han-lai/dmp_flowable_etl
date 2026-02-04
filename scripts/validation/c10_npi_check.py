import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_c10_npi_total():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_c10 = f"plant = 'WJ2' AND factory = 'NBJ' AND line = 'C10' AND {mo_filter}"
    
    sql = f"""
    SELECT 
        count(DISTINCT task_id) as total_event
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_c10}
      AND (task_start_date BETWEEN '2025-12-01' AND '2025-12-31'
           OR task_claim_date BETWEEN '2025-12-01' AND '2025-12-31'
           OR task_end_date BETWEEN '2025-12-01' AND '2025-12-31')
    """
    print("\n--- C10 Dec Event-based Total (MO 19/2) ---")
    print(client.query_df(sql))

if __name__ == "__main__":
    check_c10_npi_total()
