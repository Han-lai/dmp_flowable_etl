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

def export_v4_2_absolute_no_other():
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    # 修正：同時處理 task_claim_date 與 task_end_date 的 NULL 情況
    query = """
    SELECT 
        task_id,
        mo_number,
        substring(mo_number, 1, 3) as mo_prefix,
        task_start_date,
        task_claim_date,
        task_end_date,
        multiIf(
            -- 1. 已結案且是今日開單
            task_end_date = task_start_date, 'Done',
            -- 2. 未結案 (或跨日結案) 且今日已領
            COALESCE(task_claim_date, toDate('1900-01-01')) = task_start_date AND COALESCE(task_end_date, toDate('9999-12-31')) != task_start_date, 'Doing',
            -- 3. 未結案 (或跨日結案) 且非今日領取
            COALESCE(task_claim_date, toDate('1900-01-01')) != task_start_date AND COALESCE(task_end_date, toDate('9999-12-31')) != task_start_date, 'Todo',
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
    
    output_path = "scratch/v4.2_absolute_final_E5.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"\n[V4.2 Absolute Final Details Exported to {output_path}]")
    print("-" * 60)
    print("日分類統計對照 (Zero-Other Guaranteed):")
    summary = df.groupby(['task_start_date', 'v4_2_category']).size().unstack(fill_value=0)
    print(summary.to_string())

if __name__ == "__main__":
    export_v4_2_absolute_no_other()
