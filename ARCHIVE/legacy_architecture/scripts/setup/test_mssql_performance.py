#!/usr/bin/env python3
"""
測試 MSSQL 查詢效能
"""

import time
import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def test_mssql_query_performance():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    # 測試不同大小的查詢
    test_cases = [
        {
            'name': '小範圍查詢 (1天)',
            'table': 'APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108',
            'time_column': 'CREATE_TIME_',
            'start': '2025-10-13 15:18:55',
            'end': '2025-10-13 16:18:55'  # 1小時
        },
        {
            'name': '中範圍查詢 (半天)',
            'table': 'APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108',
            'time_column': 'CREATE_TIME_',
            'start': '2025-10-13 15:18:55',
            'end': '2025-10-14 03:18:55'  # 12小時
        },
        {
            'name': '原始錯誤批次 (1天)',
            'table': 'APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108',
            'time_column': 'CREATE_TIME_',
            'start': '2025-10-13 15:18:55',
            'end': '2025-10-14 15:18:55'  # 24小時
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🔍 測試: {test_case['name']}")
        print("-" * 60)
        
        try:
            # 測試筆數查詢
            count_sql = f"""
            SELECT count(*) FROM jdbc('mssql_master', '
                SELECT 1 FROM {test_case['table']}
                WHERE {test_case['time_column']} >= ''{test_case['start']}'' 
                  AND {test_case['time_column']} < ''{test_case['end']}''
            ')
            """
            
            start_time = time.perf_counter()
            count = client.command(count_sql)
            duration = time.perf_counter() - start_time
            
            print(f"✅ 筆數: {count:,}")
            print(f"✅ 查詢時間: {duration:.2f} 秒")
            print(f"✅ 查詢速度: {count/duration:,.0f} 筆/秒")
            
            # 如果查詢時間超過 30 秒，停止後續測試
            if duration > 30:
                print("⚠️ 查詢時間過長，停止後續測試")
                break
                
        except Exception as e:
            print(f"❌ 查詢失敗: {e}")
            break

def test_simple_mssql_connection():
    """測試基本 MSSQL 連線"""
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("🔍 測試基本 MSSQL 連線")
    print("-" * 60)
    
    try:
        # 測試簡單查詢
        simple_sql = """
        SELECT * FROM jdbc('mssql_master', '
            SELECT TOP 10 ID_, CREATE_TIME_ 
            FROM APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108
            ORDER BY CREATE_TIME_ DESC
        ')
        """
        
        start_time = time.perf_counter()
        result = client.query(simple_sql)
        duration = time.perf_counter() - start_time
        
        print(f"✅ 查詢成功: {len(result.result_rows)} 筆")
        print(f"✅ 查詢時間: {duration:.2f} 秒")
        
        if result.result_rows:
            print("✅ 最新資料:")
            for row in result.result_rows[:3]:
                print(f"  ID: {row[0]}, 時間: {row[1]}")
        
    except Exception as e:
        print(f"❌ 基本連線失敗: {e}")

if __name__ == "__main__":
    test_simple_mssql_connection()
    test_mssql_query_performance()