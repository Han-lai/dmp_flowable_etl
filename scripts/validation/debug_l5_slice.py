import clickhouse_connect
import pandas as pd

def debug_data():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    print("Checking Silver Fact Table for NBU/E5 in Dec 2025...")
    query = """
    SELECT region, plant, factory, line, task_start_date, count() as cnt
    FROM silver.mv_fact_task_vx FINAL
    WHERE factory = 'NBU' AND line = 'E5'
      AND task_start_date BETWEEN '2025-12-01' AND '2025-12-31'
    GROUP BY region, plant, factory, line, task_start_date
    LIMIT 10
    """
    try:
        df = client.query_df(query)
        print("Silver Data:")
        print(df)
    except Exception as e:
        print(f"Error querying Silver: {e}")

    print("\nChecking Gold Table combinations for CNE-WJ2...")
    query_gold = """
    SELECT DISTINCT factory, line
    FROM gold.rmv_l5_task_completion
    WHERE region = 'CNE' AND plant = 'WJ2'
      AND snapshot_date BETWEEN '2025-12-15' AND '2025-12-28'
    """
    try:
        df_gold = client.query_df(query_gold)
        print("Available Factory/Line combinations:")
        print(df_gold)
    except Exception as e:
        print(f"Error querying Gold: {e}")

if __name__ == "__main__":
    debug_data()
