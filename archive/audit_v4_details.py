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

def export_v4_details():
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    # 這個查詢會模擬 V4 的判定邏輯，從 Silver 表提取原始任務 ID 與時間
    query = """
    WITH 
        '2025-12-25' AS start_d,
        '2025-12-31' AS end_d
    SELECT 
        task_id,
        task_start_date,
        task_claim_date,
        task_end_date,
        task_definition_key as proc_key,
        -- 動態判定 V4 分類 (與 SQL 邏輯一致)
        multiIf(
            task_end_date BETWEEN start_d AND end_d, 'Done',
            task_claim_date BETWEEN start_d AND end_d AND task_end_date != task_claim_date, 'Doing',
            task_start_date BETWEEN start_d AND end_d AND task_claim_date != task_start_date AND task_end_date != task_start_date, 'Todo',
            'Other'
        ) as v4_category,
        -- 動態判定 Snapshot Date (事件發生日)
        multiIf(
            task_end_date BETWEEN start_d AND end_d, task_end_date,
            task_claim_date BETWEEN start_d AND end_d, task_claim_date,
            task_start_date BETWEEN start_d AND end_d, task_start_date,
            toDate('1900-01-01')
        ) as event_date
    FROM silver.mv_fact_task_vx FINAL
    WHERE region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5'
      AND (
        task_end_date BETWEEN start_d AND end_d OR
        task_claim_date BETWEEN start_d AND end_d OR
        task_start_date BETWEEN start_d AND end_d
      )
      AND is_excluded = 0
    ORDER BY event_date, v4_category
    """
    
    res = client.query(query)
    df = pd.DataFrame(res.result_rows, columns=res.column_names)
    
    # 儲存到 scratch 供使用者下載或查看
    output_path = "scratch/v4_audit_details_E5_Dec.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"\n[V4 Audit Details Exported to {output_path}]")
    print("-" * 50)
    print("各類別筆數統計 (Summary):")
    summary = df.groupby(['event_date', 'v4_category']).size().reset_index(name='count')
    print(summary.to_string(index=False))
    
    print("\n明細樣例 (Samples):")
    print(df[['task_id', 'v4_category', 'event_date']].head(10).to_string(index=False))

if __name__ == "__main__":
    export_v4_details()
