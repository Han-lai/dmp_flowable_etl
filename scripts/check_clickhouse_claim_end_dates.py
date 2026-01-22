#!/usr/bin/env python3
"""
檢查 ClickHouse 中任務的認領和結束日期
"""

import clickhouse_connect
import pandas as pd

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default',
            database='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def check_claim_end_dates(client):
    """檢查認領和結束日期"""
    
    print(f"🔍 檢查 199% 工單號任務在不同日期的分佈")
    query = """
    SELECT 
        mo_number, task_definition_key, task_status,
        task_create_time, task_claim_time, task_end_time,
        toDate(task_create_time) as create_date,
        toDate(task_claim_time) as claim_date,
        toDate(task_end_time) as end_date
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
        print(f"📊 199% 工單號任務詳細日期資料 ({len(df)} 筆):")
        print(df.to_string(index=False))
        
        print(f"\n🔍 檢查是否有任務在 2025-12-31 被認領")
        claim_2025_12_31 = df[df['claim_date'] == '2025-12-31']
        if len(claim_2025_12_31) > 0:
            print(f"📊 2025-12-31 認領的任務:")
            print(claim_2025_12_31.to_string(index=False))
        else:
            print("❌ 沒有任務在 2025-12-31 被認領")
        
        return df
    except Exception as e:
        print(f"❌ 查詢失敗: {e}")
        return None

def check_missing_task(client):
    """檢查是否有遺漏的任務"""
    
    print(f"\n🔍 檢查是否有任務在 2025-12-31 開始")
    query = """
    SELECT 
        mo_number, task_definition_key, task_status,
        task_create_time, task_claim_time, task_end_time,
        toDate(task_create_time) as create_date,
        toDate(task_claim_time) as claim_date,
        toDate(task_end_time) as end_date
    FROM silver.mv_fact_task_vx_attribution
    WHERE mo_number IN ('1990000003', '1990010003')
      AND plant = 'WJ2'
      AND factory = 'NBU' 
      AND line = 'E5'
      AND (
        toDate(task_create_time) = '2025-12-31'
        OR toDate(task_claim_time) = '2025-12-31'
        OR toDate(task_end_time) = '2025-12-31'
      )
    ORDER BY mo_number, task_create_time
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print(f"📊 2025-12-31 相關的任務 ({len(df)} 筆):")
        if len(df) > 0:
            print(df.to_string(index=False))
        else:
            print("❌ 沒有任務在 2025-12-31 創建/認領/結束")
        
        return df
    except Exception as e:
        print(f"❌ 查詢失敗: {e}")
        return None

def main():
    """主執行函數"""
    print("🔍 檢查 ClickHouse 認領和結束日期")
    print("="*50)
    
    client = get_clickhouse_client()
    if client is None:
        print("❌ 無法連線到 ClickHouse")
        return
    
    check_claim_end_dates(client)
    check_missing_task(client)
    
    try:
        client.close()
    except:
        pass

if __name__ == "__main__":
    main()