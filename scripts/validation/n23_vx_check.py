import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_vx_breakdown():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    # Check vx_type for events on 12/27
    sql = f"""
    SELECT 
        vx_type,
        count(DISTINCT task_id) as total_event,
        countIf(task_end_date = '2025-12-27') as ended
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND (task_start_date = '2025-12-27' OR task_claim_date = '2025-12-27' OR task_end_date = '2025-12-27')
    GROUP BY vx_type
    """
    print("\n--- N23 Vx Breakdown for 12/27 Events ---")
    print(tabulate(client.query_df(sql), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_vx_breakdown()
