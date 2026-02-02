#!/usr/bin/env python3
"""
檢查特定錯誤批次的詳細狀態
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    # 檢查特定的錯誤批次
    error_batches = [
        'ACT_HI_TASKINST_0108_20251213_151854',
        'ACT_HI_IDENTITYLINK_0108_20251013_151855'
    ]
    
    print("🔍 檢查特定錯誤批次狀態:")
    print("=" * 100)
    
    for batch_id in error_batches:
        print(f"\n📋 批次: {batch_id}")
        print("-" * 80)
        
        # 查詢批次控制記錄
        batch_sql = f"""
        SELECT table_name, batch_id, status, watermark_start, watermark_end, 
               row_count, duration_seconds, error_message, created_at, updated_at
        FROM bronze.sync_batch_control FINAL
        WHERE batch_id = '{batch_id}'
        """
        
        result = client.query(batch_sql)
        
        if result.result_rows:
            row = result.result_rows[0]
            table_name, batch_id, status, watermark_start, watermark_end, row_count, duration_seconds, error_message, created_at, updated_at = row
            
            print(f"表名: {table_name}")
            print(f"狀態: {status}")
            print(f"時間範圍: {watermark_start} ~ {watermark_end}")
            print(f"記錄筆數: {row_count:,}")
            print(f"執行時間: {duration_seconds:.2f} 秒")
            print(f"錯誤訊息: {error_message}")
            print(f"建立時間: {created_at}")
            print(f"更新時間: {updated_at}")
            
            # 檢查目標表中的實際資料
            if table_name == 'ACT_HI_TASKINST_0108':
                target_table = 'bronze.bpm_act_hi_taskinst'
                time_column = 'START_TIME_'
            elif table_name == 'ACT_HI_IDENTITYLINK_0108':
                target_table = 'bronze.bpm_act_hi_identitylink'
                time_column = 'CREATE_TIME_'
            else:
                target_table = None
                time_column = None
            
            if target_table:
                # 檢查 batch_id 資料
                batch_count_sql = f"""
                SELECT count(*) FROM {target_table}
                WHERE _batch_id = '{batch_id}'
                """
                
                try:
                    batch_count = client.command(batch_count_sql)
                    print(f"目標表中 batch_id 資料筆數: {batch_count:,}")
                except Exception as e:
                    print(f"無法查詢 batch_id 資料: {e}")
                
                # 檢查時間範圍資料
                if time_column:
                    time_count_sql = f"""
                    SELECT count(*) FROM {target_table}
                    WHERE {time_column} >= '{watermark_start}' AND {time_column} < '{watermark_end}'
                    """
                    
                    try:
                        time_count = client.command(time_count_sql)
                        print(f"目標表中時間範圍資料筆數: {time_count:,}")
                    except Exception as e:
                        print(f"無法查詢時間範圍資料: {e}")
        else:
            print(f"❌ 找不到批次記錄: {batch_id}")
    
    print("\n" + "=" * 100)

if __name__ == "__main__":
    main()