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

def export_v4_2_transparent_details():
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    # 這個查詢會將判定的「原始時間」與「判定結果」並列顯示，方便使用者核對
    query = """
    SELECT 
        task_id,
        mo_number,
        -- [判定基準日]
        task_start_date AS target_report_date,
        -- [判定結果]
        multiIf(
            task_end_date = task_start_date, 'Done',
            COALESCE(task_claim_date, toDate('1900-01-01')) = task_start_date AND COALESCE(task_end_date, toDate('9999-12-31')) != task_start_date, 'Doing',
            COALESCE(task_claim_date, toDate('1900-01-01')) != task_start_date AND COALESCE(task_end_date, toDate('9999-12-31')) != task_start_date, 'Todo',
            'Other'
        ) AS v4_2_stage,
        -- [原始時間證據]
        task_start_date,
        task_claim_date,
        task_end_date
    FROM silver.mv_fact_task_vx FINAL
    WHERE region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5'
      AND task_start_date BETWEEN '2025-12-25' AND '2025-12-31'
      AND is_excluded = 0
    ORDER BY task_start_date, v4_2_stage
    """
    
    res = client.query(query)
    df = pd.DataFrame(res.result_rows, columns=res.column_names)
    
    output_path = "scratch/v4.2_verification_details_E5.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"\n[V4.2 Verification Details Exported to {output_path}]")
    print("-" * 80)
    print("核對樣例 (E5 關鍵任務切片):")
    # 顯示不同階段各一筆樣例，讓使用者核對邏輯
    samples = []
    for stage in ['Todo', 'Doing', 'Done']:
        sample = df[df['v4_2_stage'] == stage].head(2)
        samples.append(sample)
    
    print(pd.concat(samples).to_string(index=False))

if __name__ == "__main__":
    export_v4_2_transparent_details()
