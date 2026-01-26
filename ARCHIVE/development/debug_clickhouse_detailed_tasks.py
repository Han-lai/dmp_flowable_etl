#!/usr/bin/env python3
"""
詳細調試 ClickHouse 任務資料，使用修正後的日期邏輯
"""

import clickhouse_connect
import pandas as pd

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default',
            database='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def debug_clickhouse_tasks(client, test_date='2025-12-30'):
    """詳細調試 ClickHouse 任務資料"""
    
    print(f"🔍 ClickHouse: 使用修正後的日期邏輯查詢任務")
    query = f"""
    SELECT 
        vx_type, vx_subtype, plant, factory, line,
        task_definition_key, task_status, mo_number,
        task_create_time, task_claim_time, task_end_time,
        is_excluded,
        CASE 
            WHEN toDate(task_create_time) = '{test_date}' THEN 'CREATE_MATCH'
            WHEN toDate(task_claim_time) = '{test_date}' THEN 'CLAIM_MATCH'
            WHEN toDate(task_end_time) = '{test_date}' THEN 'END_MATCH'
            ELSE 'NO_MATCH'
        END as date_match_type
    FROM silver.mv_fact_task_vx_attribution
    WHERE (
        toDate(task_create_time) = '{test_date}'
        OR toDate(task_claim_time) = '{test_date}'
        OR toDate(task_end_time) = '{test_date}'
    )
      AND plant = 'WJ2'
      AND factory = 'NBU' 
      AND line = 'E5'
      AND vx_type = 'V1'
    ORDER BY mo_number, task_create_time
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print(f"📊 ClickHouse 修正後查詢結果 ({len(df)} 筆):")
        print(df.to_string(index=False))
        
        if len(df) > 0:
            print(f"\n📈 工單號分佈:")
            mo_stats = df.groupby('mo_number').size().sort_values(ascending=False)
            for mo, count in mo_stats.items():
                print(f"  {mo}: {count} 個任務")
            
            print(f"\n📅 日期匹配類型分佈:")
            date_stats = df.groupby('date_match_type').size()
            for date_type, count in date_stats.items():
                print(f"  {date_type}: {count} 個任務")
            
            print(f"\n📊 任務狀態分佈:")
            status_stats = df.groupby('task_status').size()
            for status, count in status_stats.items():
                print(f"  {status}: {count} 個任務")
        
        return df
    except Exception as e:
        print(f"❌ ClickHouse 查詢失敗: {e}")
        return None

def main():
    """主執行函數"""
    print("🔍 ClickHouse 詳細任務調試（修正後日期邏輯）")
    print("="*60)
    
    client = get_clickhouse_client()
    if client is None:
        print("❌ 無法連線到 ClickHouse")
        return
    
    debug_clickhouse_tasks(client)
    
    try:
        client.close()
    except:
        pass

if __name__ == "__main__":
    main()