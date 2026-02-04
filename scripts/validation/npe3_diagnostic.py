import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def run_diagnostic():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    filters_npe3 = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NPE' AND line = 'NPE3'"
    dates = ['2025-12-25', '2025-12-26']
    
    for d_str in dates:
        d = pd.to_datetime(d_str).date()
        d_start = d - pd.Timedelta(days=6)
        
        print(f"\n--- Rolling 7-day Acc at {d} (Window: {d_start} ~ {d}) ---")
        
        rolling_sql = f"""
        SELECT 
            vx_type,
            count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 AND {filters_npe3}
          AND task_start_date BETWEEN '{d_start}' AND '{d}'
          AND (task_end_date IS NULL OR task_end_date > '{d}')
        GROUP BY vx_type
        """
        df = client.query_df(rolling_sql)
        print(tabulate(df, headers='keys', tablefmt='psql', showindex=False))
        print("Total Rolling Acc:", df['cnt'].sum())

if __name__ == "__main__":
    run_diagnostic()
