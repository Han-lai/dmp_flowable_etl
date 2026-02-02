#!/usr/bin/env python3
"""
檢查 ACT_HI_TASKINST_0108 表的缺失資料
"""

import clickhouse_connect
from datetime import datetime

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("🔍 檢查 ACT_HI_TASKINST_0108 缺失資料")
    print("=" * 80)
    
    # 1. 檢查批次覆蓋範圍
    print("\n📊 批次覆蓋範圍:")
    print("-" * 60)
    
    batch_sql = """
    SELECT 
        MIN(watermark_start) as earliest_batch,
        MAX(watermark_end) as latest_batch,
        COUNT(*) as batch_count,
        SUM(row_count) as total_synced
    FROM bronze.sync_batch_control FINAL
    WHERE table_name = 'ACT_HI_TASKINST_0108' 
      AND status = 'completed'
    """
    
    result = client.query(batch_sql)
    if result.result_rows:
        earliest, latest, count, synced = result.result_rows[0]
        print(f"批次時間範圍: {earliest} ~ {latest}")
        print(f"批次數量: {count}")
        print(f"已同步筆數: {synced:,}")
    
    # 2. 檢查 MSSQL vs ClickHouse 資料量
    print(f"\n📈 資料量比較:")
    print("-" * 60)
    
    # MSSQL 總筆數
    mssql_count_sql = """
    SELECT count(*) FROM jdbc('mssql_master', '
        SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108
    ')
    """
    mssql_count = client.command(mssql_count_sql)
    
    # ClickHouse 筆數
    ch_count = client.command("SELECT count(*) FROM bronze.bpm_act_hi_taskinst")
    
    print(f"MSSQL 總筆數: {mssql_count:,}")
    print(f"ClickHouse 筆數: {ch_count:,}")
    print(f"缺失筆數: {mssql_count - ch_count:,}")
    print(f"覆蓋率: {ch_count/mssql_count*100:.2f}%")
    
    # 3. 檢查時間範圍缺口
    print(f"\n🕐 時間範圍分析:")
    print("-" * 60)
    
    # MSSQL 時間範圍
    mssql_range_sql = """
    SELECT min_time, max_time FROM jdbc('mssql_master', '
        SELECT 
            MIN(START_TIME_) as min_time,
            MAX(START_TIME_) as max_time
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108
        WHERE START_TIME_ IS NOT NULL
    ')
    """
    
    mssql_result = client.query(mssql_range_sql)
    if mssql_result.result_rows:
        mssql_min, mssql_max = mssql_result.result_rows[0]
        print(f"MSSQL 時間範圍: {mssql_min} ~ {mssql_max}")
    
    # 批次覆蓋範圍 (重複顯示以便比較)
    print(f"批次覆蓋範圍: {earliest} ~ {latest}")
    
    # 4. 檢查缺失的時間段
    if mssql_result.result_rows:
        mssql_min_dt = datetime.fromisoformat(str(mssql_min).replace('T', ' '))
        mssql_max_dt = datetime.fromisoformat(str(mssql_max).replace('T', ' '))
        batch_max_dt = datetime.fromisoformat(str(latest))
        
        if batch_max_dt < mssql_max_dt:
            missing_days = (mssql_max_dt - batch_max_dt).days
            print(f"\n⚠️ 發現缺失時間範圍:")
            print(f"缺失範圍: {latest} ~ {mssql_max}")
            print(f"缺失天數: {missing_days} 天")
            
            # 估算缺失資料量
            missing_data_sql = f"""
            SELECT count(*) FROM jdbc('mssql_master', '
                SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108
                WHERE START_TIME_ > ''{latest}''
                  AND START_TIME_ IS NOT NULL
            ')
            """
            
            try:
                missing_count = client.command(missing_data_sql)
                print(f"估算缺失筆數: {missing_count:,}")
            except Exception as e:
                print(f"無法查詢缺失筆數: {e}")
    
    # 5. 檢查是否有失敗的批次
    print(f"\n❌ 失敗批次檢查:")
    print("-" * 60)
    
    failed_sql = """
    SELECT 
        batch_id,
        watermark_start,
        watermark_end,
        error_message
    FROM bronze.sync_batch_control FINAL
    WHERE table_name = 'ACT_HI_TASKINST_0108' 
      AND status = 'failed'
    ORDER BY watermark_start
    """
    
    failed_result = client.query(failed_sql)
    if failed_result.result_rows:
        print("發現失敗批次:")
        for batch_id, start, end, error in failed_result.result_rows:
            print(f"  {batch_id}: {start} ~ {end}")
            print(f"    錯誤: {error[:100]}...")
    else:
        print("✅ 沒有失敗的批次")

if __name__ == "__main__":
    main()