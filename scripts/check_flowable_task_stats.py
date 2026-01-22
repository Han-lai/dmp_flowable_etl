#!/usr/bin/env python3
"""
檢查 bronze.common_flowable_task_stats 中的 WJ2+NBU+E5 資料
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

def check_flowable_task_stats(client, test_date='2025-12-30'):
    """檢查 FlowableTaskStats 資料"""
    
    print(f"\n🔍 檢查 {test_date} 的 FlowableTaskStats 資料")
    query = f"""
    SELECT 
        Plant, Factory, Line, 
        TaskDefinitionKey, TaskStatus,
        TaskCreateTime, TaskClaimTime, TaskEndTime,
        MoNumber, ProcessInstanceId
    FROM bronze.common_flowable_task_stats
    WHERE TaskCreateDate = '{test_date}'
      AND Plant = 'WJ2'
      AND Factory = 'NBU'
      AND Line = 'E5'
    ORDER BY TaskCreateTime
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print(f"📊 找到 {len(df)} 筆 WJ2+NBU+E5 資料:")
        if len(df) > 0:
            print(df.to_string(index=False))
        else:
            print("❌ 沒有找到符合條件的資料")
    except Exception as e:
        print(f"❌ 查詢失敗: {e}")
        return
    
    # 檢查是否有其他日期欄位的資料
    print(f"\n🔍 檢查其他日期欄位")
    query2 = f"""
    SELECT 
        Plant, Factory, Line, 
        TaskDefinitionKey, TaskStatus,
        TaskCreateDate, TaskClaimDate, TaskEndDate,
        COUNT(*) as task_count
    FROM bronze.common_flowable_task_stats
    WHERE (
        TaskCreateDate = '{test_date}'
        OR TaskClaimDate = '{test_date}'
        OR TaskEndDate = '{test_date}'
    )
    AND Plant = 'WJ2'
    AND Factory = 'NBU'
    AND Line = 'E5'
    GROUP BY Plant, Factory, Line, TaskDefinitionKey, TaskStatus, TaskCreateDate, TaskClaimDate, TaskEndDate
    ORDER BY task_count DESC
    """
    
    try:
        result2 = client.query(query2)
        df2 = pd.DataFrame(result2.result_rows, columns=result2.column_names)
        print(f"📊 按日期欄位查詢結果:")
        if len(df2) > 0:
            print(df2.to_string(index=False))
        else:
            print("❌ 沒有找到符合條件的資料")
    except Exception as e:
        print(f"❌ 查詢失敗: {e}")
        return
    
    # 檢查 WJ2 的所有資料
    print(f"\n🔍 檢查 WJ2 的所有資料樣本")
    query3 = f"""
    SELECT 
        Plant, Factory, Line, 
        TaskDefinitionKey, TaskStatus,
        COUNT(*) as task_count
    FROM bronze.common_flowable_task_stats
    WHERE TaskCreateDate = '{test_date}'
      AND Plant = 'WJ2'
    GROUP BY Plant, Factory, Line, TaskDefinitionKey, TaskStatus
    ORDER BY task_count DESC
    LIMIT 20
    """
    
    try:
        result3 = client.query(query3)
        df3 = pd.DataFrame(result3.result_rows, columns=result3.column_names)
        print(f"📊 WJ2 資料樣本:")
        if len(df3) > 0:
            print(df3.to_string(index=False))
        else:
            print("❌ 沒有找到 WJ2 的資料")
    except Exception as e:
        print(f"❌ 查詢失敗: {e}")

def main():
    """主執行函數"""
    print("🔍 FlowableTaskStats 資料檢查")
    print("="*50)
    
    client = get_clickhouse_client()
    if client is None:
        return
    
    check_flowable_task_stats(client)
    
    try:
        client.close()
    except:
        pass

if __name__ == "__main__":
    main()