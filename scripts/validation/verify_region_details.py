import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def extract_details():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    
    print("--- 🔍 WJ-WJ2-NBU-E5 記錄明細 (Silver Fact Layer) ---")
    query = """
    SELECT 
        task_id,
        proc_inst_id,
        task_start_date,
        region,
        region_source,
        plant,
        factory,
        line,
        vx_type,
        mo_number
    FROM silver.mv_fact_task_vx FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND task_start_date BETWEEN '2025-12-22' AND '2025-12-28'
    LIMIT 10
    """
    try:
        df = client.query_df(query)
        print(tabulate(df, headers='keys', tablefmt='psql', showindex=False))
    except Exception as e:
        print(f"Error: {e}")

    print("\n--- 🔍 CNE Region 的資料檢查 (Dec 15 ~ Dec 28) ---")
    query_cne = """
    SELECT 
        region, plant, factory, line, count() as row_count
    FROM silver.mv_fact_task_vx FINAL
    WHERE region = 'CNE'
      AND task_start_date BETWEEN '2025-12-15' AND '2025-12-28'
    GROUP BY region, plant, factory, line
    LIMIT 10
    """
    try:
        df_cne = client.query_df(query_cne)
        print(tabulate(df_cne, headers='keys', tablefmt='psql', showindex=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extract_details()
