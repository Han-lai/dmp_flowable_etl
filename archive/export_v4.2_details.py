import clickhouse_connect
import pandas as pd
import os

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', '10.146.206.76'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', '1qaz2wsx3edc'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

def export_v4_2_details():
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    # 使用 V4.2 最終判定邏輯 (寬鬆完工模式)
    query = """
    SELECT 
        task_id,
        mo_number,
        substring(mo_number, 1, 3) as mo_prefix,
        task_start_date,
        task_claim_date,
        task_end_date,
        -- V4.2 互斥分類
        multiIf(
            task_end_date = task_start_date, 'Done',
            task_claim_date = task_start_date AND task_end_date != task_start_date, 'Doing',
            task_claim_date != task_start_date AND task_end_date != task_start_date, 'Todo',
            'Other'
        ) as v4_2_category
    FROM silver.mv_fact_task_vx FINAL
    WHERE region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5'
      AND task_start_date BETWEEN '2025-12-25' AND '2025-12-31'
      AND is_excluded = 0
    ORDER BY task_start_date, v4_2_category
    """
    
    res = client.query(query)
    df = pd.DataFrame(res.result_rows, columns=res.column_names)
    
    output_path = "scratch/v4.2_final_details_E5.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"\n[V4.2 Final Details Exported to {output_path}]")
    print("-" * 60)
    print("日分類統計對照 (Daily Summary):")
    summary = df.groupby(['task_start_date', 'v4_2_category']).size().unstack(fill_value=0)
    print(summary.to_string())
    
    print("\n明細樣例 (V4.2 Samples):")
    print(df[['task_id', 'mo_prefix', 'v4_2_category']].head(10).to_string(index=False))

if __name__ == "__main__":
    export_v4_2_details()
