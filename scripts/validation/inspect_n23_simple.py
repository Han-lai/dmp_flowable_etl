import clickhouse_connect
import pandas as pd

def inspect_n23_simple():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    mo_filter = "(mo_number LIKE '19%' OR mo_number LIKE '2%')"
    filters_n23 = f"region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'N23' AND {mo_filter}"
    
    sql = f"""
    SELECT 
        task_id,
        task_name,
        task_definition_key,
        task_end_date
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0 AND {filters_n23}
      AND task_end_date = '2025-12-27'
    """
    df = client.query_df(sql)
    print(f"Total found: {len(df)}")
    if not df.empty:
        for i, row in df.iterrows():
            print(f"{i}: {row['task_name']} | {row['task_definition_key']}")

if __name__ == "__main__":
    inspect_n23_simple()
