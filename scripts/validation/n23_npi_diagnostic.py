import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_n23_npi_logic():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    # Logic: MO starts with 19 or 2 (NPI/Prototype pattern)
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    dates = ['2025-12-25', '2025-12-26', '2025-12-27', '2025-12-28', '2025-12-29', '2025-12-30', '2025-12-31']
    
    results = []
    for d in dates:
        sql = f"""
        SELECT 
            count() as total,
            countIf(task_end_date = '{d}') as done,
            countIf(task_claim_date = '{d}' AND (task_end_date > '{d}' OR task_end_date IS NULL)) as doing
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 AND {filters_n23}
          AND task_start_date = '{d}'
        """
        df = client.query_df(sql)
        row = df.iloc[0].to_dict()
        row['date'] = d
        row['todo'] = row['total'] - row['done'] - row['doing']
        results.append(row)
    
    print("\n--- N23 Daily Totals (MO Starts with 19 or 2) ---")
    print(tabulate(pd.DataFrame(results), headers='keys', tablefmt='psql', showindex=False))

    # Check Acc logic for N23
    # User's Acc: 12/25 (9), 12/26 (10), 12/27 (8), 12/28 (8), 12/29 (4), 12/30 (2), 12/31 (2)
    acc_results = []
    for d in dates:
        sql_acc = f"""
        SELECT count() as acc
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 AND {filters_n23}
          AND task_start_date <= '{d}'
          AND (task_end_date > '{d}' OR task_end_date IS NULL)
        """
        acc_val = client.query_df(sql_acc).iloc[0,0]
        acc_results.append({'date': d, 'acc': acc_val})
    
    print("\n--- N23 Acc (MO Starts with 19 or 2, NO 7-day limit) ---")
    print(tabulate(pd.DataFrame(acc_results), headers='keys', tablefmt='psql', showindex=False))

    # Test with 7-day rolling limit
    rolling_acc_results = []
    for d_str in dates:
        d_obj = pd.to_datetime(d_str).date()
        d_start = d_obj - pd.Timedelta(days=6)
        sql_rolling = f"""
        SELECT count() as acc
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 AND {filters_n23}
          AND task_start_date BETWEEN '{d_start}' AND '{d_str}'
          AND (task_end_date > '{d_str}' OR task_end_date IS NULL)
        """
        acc_val = client.query_df(sql_rolling).iloc[0,0]
        rolling_acc_results.append({'date': d_str, 'acc': acc_val})
    
    print("\n--- N23 Acc (MO Starts with 19 or 2, WITH 7-day limit) ---")
    print(tabulate(pd.DataFrame(rolling_acc_results), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_n23_npi_logic()
