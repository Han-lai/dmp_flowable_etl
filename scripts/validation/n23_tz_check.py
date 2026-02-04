import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def check_timezone_effect():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    # Aggregated UTC+8 view
    sql_agg = f"""
    SELECT 
        toDate(addHours(toDateTime(task_start_time), 8)) as date_l,
        count() as total,
        countIf(toDate(addHours(toDateTime(task_end_time), 8)) = date_l) as done_today
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_start_date BETWEEN '2025-12-20' AND '2025-12-31'
    GROUP BY date_l
    ORDER BY date_l
    """
    df = client.query_df(sql_agg)
    print("\n--- N23 Daily (UTC+8, MO 19/2) ---")
    print(tabulate(df, headers='keys', tablefmt='psql', showindex=False))

    # Check Acc with TZ8
    acc_results = []
    dates = ['2025-12-25', '2025-12-26', '2025-12-31']
    for d_str in dates:
        d_obj = pd.to_datetime(d_str).date()
        d_start = d_obj - pd.Timedelta(days=6)
        sql_acc = f"""
        SELECT count() as acc
        FROM silver.mv_fact_task_vx FINAL
        WHERE is_excluded = 0 AND {filters_n23}
          AND toDate(addHours(toDateTime(task_start_time), 8)) BETWEEN '{d_start}' AND '{d_str}'
          AND (task_end_time IS NULL OR toDate(addHours(toDateTime(task_end_time), 8)) > '{d_str}')
        """
        acc_val = client.query_df(sql_acc).iloc[0,0]
        acc_results.append({'date': d_str, 'acc': acc_val})
    
    print("\n--- N23 Acc (UTC+8, MO 19/2, 7-day Rolling) ---")
    print(tabulate(pd.DataFrame(acc_results), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    check_timezone_effect()
