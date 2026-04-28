import clickhouse_connect
import pandas as pd
import os

CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', 'REDACTED_IP'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', 'REDACTED_PASSWORD'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

def export_v4_1_details():
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    # 執行 V4.1 嚴格判定邏輯
    query = """
    SELECT 
        task_id,
        mo_number,
        substring(mo_number, 1, 3) as mo_prefix,
        task_start_date,
        task_claim_date,
        task_end_date,
        -- V4.1 互斥分類
        multiIf(
            task_claim_date = task_start_date AND task_end_date = task_start_date, 'Done',
            task_claim_date = task_start_date AND task_end_date != task_start_date, 'Doing',
            task_claim_date != task_start_date AND task_end_date != task_start_date, 'Todo',
            'Other'
        ) as v4_1_category
    FROM silver.mv_fact_task_vx FINAL
    WHERE region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5'
      AND task_start_date BETWEEN '2025-12-25' AND '2025-12-31'
      AND is_excluded = 0
    ORDER BY task_start_date, v4_1_category
    """
    
    res = client.query(query)
    df = pd.DataFrame(res.result_rows, columns=res.column_names)
    
    output_path = "scratch/v4.1_details_E5_Dec.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"\n[V4.1 Details Exported to {output_path}]")
    print("-" * 60)
    print("日分類統計對照 (Daily Summary):")
    summary = df.groupby(['task_start_date', 'v4_1_category']).size().unstack(fill_value=0)
    # 確保欄位順序
    for col in ['Todo', 'Doing', 'Done']:
        if col not in summary.columns: summary[col] = 0
    print(summary[['Todo', 'Doing', 'Done']].to_string())
    
    print("\n明細樣例 (V4.1 Samples):")
    print(df[['task_id', 'mo_prefix', 'task_start_date', 'v4_1_category']].head(15).to_string(index=False))

if __name__ == "__main__":
    export_v4_1_details()
