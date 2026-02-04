import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def run_analysis():
    # ClickHouse connection parameters
    host = 'REDACTED_IP'
    port = 8121
    username = 'default'
    password = 'default'

    client = clickhouse_connect.get_client(host=host, port=port, username=username, password=password)

    print("--- Step 1: 符合條件的廠線清單 (TODO > 0, DOING > 0, DONE > 0) ---")
    
    query_step1 = """
    SELECT
        snapshot_date AS "日期",
        plant AS "廠別",
        line AS "線別",
        todo_count,
        doing_count,
        done_count
    FROM gold.rmv_l5_task_completion
    WHERE todo_count > 0 AND doing_count > 0 AND done_count > 0
    ORDER BY snapshot_date DESC, plant, line
    """
    
    result_step1 = client.query(query_step1)
    df_step1 = pd.DataFrame(result_step1.result_set, columns=result_step1.column_names)

    if df_step1.empty:
        print("未找到符合三態同時出現的資料。")
    else:
        print(tabulate(df_step1, headers='keys', tablefmt='psql', showindex=False))

    print("\n--- Step 2: 彙總結果 ---")
    
    if df_step1.empty:
        print("無統計資料。")
    else:
        unique_plants = df_step1["廠別"].nunique()
        unique_lines = df_step1["線別"].nunique()
        
        # Frequency analysis
        freq_df = df_step1.groupby(["廠別", "線別"]).size().reset_index(name="出現次數").sort_values("出現次數", ascending=False)
        
        print(f"1. 總共有 {unique_plants} 個廠別符合。")
        print(f"2. 總共有 {unique_lines} 條線別符合。")
        print("3. 最常同時出現三態的廠線：")
        print(tabulate(freq_df.head(10), headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    run_analysis()
