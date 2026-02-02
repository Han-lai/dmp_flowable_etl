#!/usr/bin/env python3
"""
檢查同步批次狀態
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
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        
        print("📊 ACT_HI_IDENTITYLINK_0108 同步狀態:")
        print("-" * 40)
        
        result = client.query("""
            SELECT status, count(*) 
            FROM bronze.sync_batch_control FINAL 
            WHERE table_name = 'ACT_HI_IDENTITYLINK_0108' 
            GROUP BY status
        """)
        
        if result.result_rows:
            for status, count in result.result_rows:
                print(f"{status:<15}: {count}")
        else:
            print("沒有找到批次記錄")
            
        # 檢查是否有失敗的批次並顯示錯誤
        error_result = client.query("""
            SELECT batch_id, error_message 
            FROM bronze.sync_batch_control FINAL 
            WHERE table_name = 'ACT_HI_IDENTITYLINK_0108' 
              AND status = 'failed' 
            LIMIT 1
        """)
        
        if error_result.result_rows:
            print("\n❌ 最新失敗錯誤訊息:")
            print(f"Batch: {error_result.result_rows[0][0]}")
            print(f"Error: {error_result.result_rows[0][1]}")
            
    except Exception as e:
        print(f"查詢失敗: {e}")

if __name__ == "__main__":
    main()
