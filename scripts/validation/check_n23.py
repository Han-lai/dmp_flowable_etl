import clickhouse_connect
import pandas as pd

def check_n23():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    sql = """
    SELECT region, plant, factory, line, vx_type, is_excluded, count() as cnt
    FROM silver.mv_fact_task_vx FINAL 
    WHERE plant='WJ2' AND line LIKE '%N23%'
    GROUP BY region, plant, factory, line, vx_type, is_excluded
    """
    print(client.query_df(sql))

if __name__ == "__main__":
    check_n23()
