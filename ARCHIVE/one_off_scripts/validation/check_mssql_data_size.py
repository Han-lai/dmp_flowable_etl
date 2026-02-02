#!/usr/bin/env python3
"""
檢查 MSSQL 資料量
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    # 檢查兩個錯誤批次的資料量
    batches = [
        {
            'name': 'ACT_HI_TASKINST_0108_20251213_151854',
            'source': 'APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108',
            'time_column': 'START_TIME_',
            'start': '2025-12-13 15:18:54',
            'end': '2025-12-16 15:18:54'
        },
        {
            'name': 'ACT_HI_IDENTITYLINK_0108_20251013_151855',
            'source': 'APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108',
            'time_column': 'CREATE_TIME_',
            'start': '2025-10-13 15:18:55',
            'end': '2025-10-14 15:18:55'
        }
    ]
    
    for batch in batches:
        print(f"\n📊 檢查批次: {batch['name']}")
        print("-" * 80)
        
        try:
            # 檢查資料筆數
            count_sql = f"""
            SELECT count(*) FROM jdbc('mssql_master', '
                SELECT 1 FROM {batch['source']}
                WHERE {batch['time_column']} >= ''{batch['start']}'' 
                  AND {batch['time_column']} < ''{batch['end']}''
            ')
            """
            
            print(f"查詢: {batch['source']}")
            print(f"時間範圍: {batch['start']} ~ {batch['end']}")
            print("正在查詢資料筆數...")
            
            # 設定較短的超時時間
            result = client.command(count_sql)
            print(f"✅ 資料筆數: {result:,}")
            
        except Exception as e:
            if "timeout" in str(e).lower():
                print(f"⚠️ 查詢超時: {e}")
                
                # 嘗試查詢整個表的資料量
                try:
                    total_count_sql = f"""
                    SELECT count(*) FROM jdbc('mssql_master', '
                        SELECT 1 FROM {batch['source']}
                    ')
                    """
                    total_result = client.command(total_count_sql)
                    print(f"📈 整個表總筆數: {total_result:,}")
                except Exception as e2:
                    print(f"❌ 無法查詢總筆數: {e2}")
            else:
                print(f"❌ 查詢失敗: {e}")

if __name__ == "__main__":
    main()