import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_full_event_total():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    dates = ['2025-12-25', '2025-12-26', '2025-12-27', '2025-12-28', '2025-12-29', '2025-12-30', '2025-12-31']
    
    results = []
    for d in dates:
        sql = f"""
        SELECT 
            count(DISTINCT task_id) as total_event
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 AND {filters_n23}
          AND (task_start_date = '{d}' OR task_claim_date = '{d}' OR task_end_date = '{d}')
        """
        df = client.query_df(sql)
        row = df.iloc[0].to_dict()
        row['date'] = d
        results.append(row)
    
    print("\n--- N23 Daily Event-based Total (Start OR Claim OR End) ---")
    print(tabulate(pd.DataFrame(results), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_full_event_total()
