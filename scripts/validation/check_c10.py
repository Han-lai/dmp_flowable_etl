import clickhouse_connect
import pandas as pd

def check_c10_dates():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    sql = """
    SELECT task_start_date, count() as cnt
    FROM silver.mv_fact_task_vx FINAL 
    WHERE plant='WJ2' AND line = 'C10' AND is_excluded = 0
      AND task_start_date BETWEEN '2025-12-01' AND '2025-12-31'
    GROUP BY task_start_date
    ORDER BY task_start_date
    """
    print(client.query_df(sql))

if __name__ == "__main__":
    check_c10_dates()
