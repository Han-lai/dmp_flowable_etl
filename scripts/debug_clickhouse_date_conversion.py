#!/usr/bin/env python3
"""
調試 ClickHouse 日期轉換問題
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

def debug_date_conversion(client):
    """調試日期轉換"""
    
    print(f"🔍 調試日期轉換和匹配邏輯")
    query = """
    SELECT 
        mo_number, task_definition_key, task_status,
        task_create_time, task_claim_time, task_end_time,
        toDate(task_create_time) as create_date,
        toDate(task_claim_time) as claim_date,
        toDate(task_end_time) as end_date,
        -- 檢查每個日期是否匹配 2025-12-30
        toDate(task_create_time) = '2025-12-30' as create_match_1230,
        toDate(task_claim_time) = '2025-12-30' as claim_match_1230,
        toDate(task_end_time) = '2025-12-30' as end_match_1230,
        -- 檢查每個日期是否匹配 2025-12-31
        toDate(task_create_time) = '2025-12-31' as create_match_1231,
        toDate(task_claim_time) = '2025-12-31' as claim_match_1231,
        toDate(task_end_time) = '2025-12-31' as end_match_1231,
        -- 檢查是否應該被包含在 2025-12-30 的查詢中
        (toDate(task_create_time) = '2025-12-30' OR toDate(task_claim_time) = '2025-12-30' OR toDate(task_end_time) = '2025-12-30') as should_match_1230
    FROM silver.mv_fact_task_vx_attribution
    WHERE mo_number IN ('1990000003', '1990010003')
      AND plant = 'WJ2'
      AND factory = 'NBU' 
      AND line = 'E5'
    ORDER BY mo_number, task_create_time
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print(f"📊 日期轉換調試結果 ({len(df)} 筆):")
        print(df.to_string(index=False))
        
        print(f"\n📊 應該匹配 2025-12-30 的任務:")
        should_match = df[df['should_match_1230'] == True]
        print(f"共 {len(should_match)} 筆任務應該被包含在 2025-12-30 查詢中")
        
        return df
    except Exception as e:
        print(f"❌ 查詢失敗: {e}")
        return None

def main():
    """主執行函數"""
    print("🔍 調試 ClickHouse 日期轉換")
    print("="*50)
    
    client = get_clickhouse_client()
    if client is None:
        print("❌ 無法連線到 ClickHouse")
        return
    
    debug_date_conversion(client)
    
    try:
        client.close()
    except:
        pass

if __name__ == "__main__":
    main()