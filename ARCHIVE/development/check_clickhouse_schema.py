#!/usr/bin/env python3
"""
檢查 ClickHouse 表結構
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

def check_table_schema(client):
    """檢查表結構"""
    
    print("🔍 檢查 silver.mv_fact_task_vx_attribution 表結構")
    query = """
    DESCRIBE silver.mv_fact_task_vx_attribution
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print("📊 表結構:")
        print(df.to_string(index=False))
        
        # 找出時間相關欄位
        time_columns = [col for col in df['name'] if 'time' in col.lower()]
        print(f"\n⏰ 時間相關欄位: {time_columns}")
        
    except Exception as e:
        print(f"❌ 查詢失敗: {e}")
        return
    
    print("\n🔍 檢查表中的樣本資料")
    sample_query = """
    SELECT *
    FROM silver.mv_fact_task_vx_attribution
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    LIMIT 3
    """
    
    try:
        result = client.query(sample_query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print("📊 樣本資料:")
        print(df.to_string(index=False))
        
    except Exception as e:
        print(f"❌ 樣本查詢失敗: {e}")

def main():
    """主執行函數"""
    print("🔍 檢查 ClickHouse 表結構")
    print("="*50)
    
    client = get_clickhouse_client()
    if client is None:
        print("❌ 無法連線到 ClickHouse")
        return
    
    check_table_schema(client)
    
    try:
        client.close()
    except:
        pass

if __name__ == "__main__":
    main()