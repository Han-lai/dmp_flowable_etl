import clickhouse_connect
import pandas as pd

def check_end_dates():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    sql = """
    SELECT task_end_date, count() as cnt
    FROM silver.mv_fact_task_vx FINAL 
    WHERE line = 'N23' AND (mo_number LIKE '19%' OR mo_number LIKE '2%')
      AND task_end_date BETWEEN '2025-12-20' AND '2025-12-31'
    GROUP BY task_end_date
    ORDER BY task_end_date
    """
    print(client.query_df(sql))

if __name__ == "__main__":
    check_end_dates()
