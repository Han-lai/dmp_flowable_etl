#!/usr/bin/env python3
"""
調試 ClickHouse 資料來源，檢查 WJ2+NBU+E5 資料的實際來源
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

def debug_clickhouse_data(client, test_date='2025-12-30'):
    """調試 ClickHouse 資料來源"""
    
    print(f"\n🔍 Step 1: 檢查 Silver 層 L5 metrics 資料")
    query1 = f"""
    SELECT 
        vx_type, plant, factory, line, snapshot_date,
        todo_qty, doing_qty, done_qty, total_task_qty
    FROM silver.mv_l5_metrics_realtime
    WHERE snapshot_date = '{test_date}'
      AND plant = 'WJ2'
      AND factory = 'NBU' 
      AND line = 'E5'
    """
    
    try:
        result1 = client.query(query1)
        df1 = pd.DataFrame(result1.result_rows, columns=result1.column_names)
        print(f"📊 Silver L5 metrics 資料:")
        print(df1.to_string(index=False))
    except Exception as e:
        print(f"❌ Step 1 失敗: {e}")
        return
    
    print(f"\n🔍 Step 2: 檢查 Silver 層 fact_task_vx_attribution 資料")
    query2 = f"""
    SELECT 
        vx_type, plant, factory, line, 
        task_status, task_definition_key,
        COUNT(*) as task_count
    FROM silver.mv_fact_task_vx_attribution
    WHERE toDate(task_create_time) = '{test_date}'
      AND plant = 'WJ2'
      AND factory = 'NBU' 
      AND line = 'E5'
    GROUP BY vx_type, plant, factory, line, task_status, task_definition_key
    ORDER BY task_count DESC
    """
    
    try:
        result2 = client.query(query2)
        df2 = pd.DataFrame(result2.result_rows, columns=result2.column_names)
        print(f"📊 Silver fact_task_vx_attribution 資料:")
        print(df2.to_string(index=False))
    except Exception as e:
        print(f"❌ Step 2 失敗: {e}")
        return
    
    print(f"\n🔍 Step 3: 檢查 Bronze 層原始資料")
    query3 = f"""
    SELECT 
        BUSINESS_KEY_, TASK_DEF_KEY_, 
        START_TIME_, CLAIM_TIME_, END_TIME_,
        ASSIGNEE_
    FROM bronze.bpm_act_hi_taskinst
    WHERE (
        toDate(START_TIME_) = '{test_date}'
        OR toDate(CLAIM_TIME_) = '{test_date}'
        OR toDate(END_TIME_) = '{test_date}'
    )
    AND BUSINESS_KEY_ LIKE '%WJ2%'
    AND BUSINESS_KEY_ LIKE '%NBU%'
    AND BUSINESS_KEY_ LIKE '%E5%'
    LIMIT 10
    """
    
    try:
        result3 = client.query(query3)
        df3 = pd.DataFrame(result3.result_rows, columns=result3.column_names)
        print(f"📊 Bronze 層原始資料:")
        print(df3.to_string(index=False))
    except Exception as e:
        print(f"❌ Step 3 失敗: {e}")
        return
    
    print(f"\n🔍 Step 4: 檢查 Bronze 層 BUSINESS_KEY 樣本")
    query4 = f"""
    SELECT DISTINCT BUSINESS_KEY_
    FROM bronze.bpm_act_hi_taskinst
    WHERE (
        toDate(START_TIME_) = '{test_date}'
        OR toDate(CLAIM_TIME_) = '{test_date}'
        OR toDate(END_TIME_) = '{test_date}'
    )
    AND BUSINESS_KEY_ LIKE '%WJ2%'
    LIMIT 20
    """
    
    try:
        result4 = client.query(query4)
        df4 = pd.DataFrame(result4.result_rows, columns=result4.column_names)
        print(f"📊 Bronze 層 BUSINESS_KEY 樣本:")
        for key in df4['BUSINESS_KEY_']:
            print(f"  {key}")
    except Exception as e:
        print(f"❌ Step 4 失敗: {e}")
        return

def main():
    """主執行函數"""
    print("🔍 ClickHouse 資料來源調試")
    print("="*50)
    
    client = get_clickhouse_client()
    if client is None:
        print("❌ 無法連線到 ClickHouse")
        return
    
    debug_clickhouse_data(client)
    
    try:
        client.close()
    except:
        pass

if __name__ == "__main__":
    main()