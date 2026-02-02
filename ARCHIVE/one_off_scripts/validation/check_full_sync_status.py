#!/usr/bin/env python3
"""
檢查完整同步狀況
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
    
    print("🔍 檢查完整同步狀況")
    print("=" * 80)
    
    # 檢查各表的 MSSQL 總筆數 vs ClickHouse 筆數
    tables_to_check = [
        {
            'name': 'ACT_HI_IDENTITYLINK_0108',
            'mssql_table': 'APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108',
            'clickhouse_table': 'bronze.bpm_act_hi_identitylink'
        },
        {
            'name': 'ACT_HI_TASKINST_0108',
            'mssql_table': 'APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108',
            'clickhouse_table': 'bronze.bpm_act_hi_taskinst'
        },
        {
            'name': 'ACT_HI_PROCINST_0108',
            'mssql_table': 'APP_SRV_BPM.dbo.ACT_HI_PROCINST_0108',
            'clickhouse_table': 'bronze.bpm_act_hi_procinst'
        }
    ]
    
    for table_info in tables_to_check:
        print(f"\n📊 表格: {table_info['name']}")
        print("-" * 60)
        
        try:
            # 查詢 MSSQL 總筆數
            mssql_count_sql = f"""
            SELECT count(*) FROM jdbc('mssql_master', '
                SELECT 1 FROM {table_info['mssql_table']}
            ')
            """
            
            print("正在查詢 MSSQL 總筆數...")
            mssql_count = client.command(mssql_count_sql)
            print(f"✅ MSSQL 總筆數: {mssql_count:,}")
            
            # 查詢 ClickHouse 筆數
            clickhouse_count = client.command(f"SELECT count(*) FROM {table_info['clickhouse_table']}")
            print(f"✅ ClickHouse 筆數: {clickhouse_count:,}")
            
            # 計算差異
            diff = mssql_count - clickhouse_count
            coverage = (clickhouse_count / mssql_count * 100) if mssql_count > 0 else 0
            
            print(f"📈 同步覆蓋率: {coverage:.2f}%")
            print(f"📉 缺失筆數: {diff:,}")
            
            if diff > 0:
                print(f"⚠️ 需要同步 {diff:,} 筆資料")
            else:
                print("✅ 同步完整")
                
        except Exception as e:
            if "timeout" in str(e).lower():
                print(f"⚠️ MSSQL 查詢超時: {e}")
                
                # 只查詢 ClickHouse 筆數
                try:
                    clickhouse_count = client.command(f"SELECT count(*) FROM {table_info['clickhouse_table']}")
                    print(f"✅ ClickHouse 筆數: {clickhouse_count:,}")
                    print("❓ MSSQL 筆數: 無法查詢（超時）")
                except Exception as e2:
                    print(f"❌ ClickHouse 查詢也失敗: {e2}")
            else:
                print(f"❌ 查詢失敗: {e}")
    
    # 檢查批次同步的時間範圍覆蓋
    print(f"\n🕐 檢查批次同步時間範圍")
    print("-" * 60)
    
    try:
        # 查詢批次控制表中的時間範圍
        batch_range_sql = """
        SELECT 
            table_name,
            MIN(watermark_start) as earliest_start,
            MAX(watermark_end) as latest_end,
            COUNT(*) as batch_count,
            SUM(row_count) as total_synced_rows
        FROM bronze.sync_batch_control FINAL
        WHERE status = 'completed'
        GROUP BY table_name
        ORDER BY table_name
        """
        
        result = client.query(batch_range_sql)
        
        for row in result.result_rows:
            table_name, earliest_start, latest_end, batch_count, total_synced_rows = row
            print(f"📋 {table_name}:")
            print(f"  時間範圍: {earliest_start} ~ {latest_end}")
            print(f"  批次數量: {batch_count}")
            print(f"  已同步筆數: {total_synced_rows:,}")
            
    except Exception as e:
        print(f"❌ 查詢批次範圍失敗: {e}")

if __name__ == "__main__":
    main()