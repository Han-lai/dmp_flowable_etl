#!/usr/bin/env python3
"""
檢查缺失的批次
"""

import clickhouse_connect
from datetime import datetime, timedelta

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("🔍 檢查缺失的批次")
    print("=" * 80)
    
    # 檢查 ACT_HI_IDENTITYLINK_0108 的批次狀況
    print("\n📊 ACT_HI_IDENTITYLINK_0108 批次詳情:")
    print("-" * 60)
    
    batch_sql = """
    SELECT 
        batch_id,
        watermark_start,
        watermark_end,
        status,
        row_count,
        error_message
    FROM bronze.sync_batch_control FINAL
    WHERE table_name = 'ACT_HI_IDENTITYLINK_0108'
    ORDER BY watermark_start
    """
    
    result = client.query(batch_sql)
    
    for row in result.result_rows:
        batch_id, start, end, status, row_count, error_msg = row
        print(f"批次: {batch_id}")
        print(f"  時間: {start} ~ {end}")
        print(f"  狀態: {status}, 筆數: {row_count:,}")
        if error_msg:
            print(f"  錯誤: {error_msg[:100]}...")
        print()
    
    # 檢查是否有更多批次應該被創建
    print("🔍 分析缺失的時間範圍:")
    print("-" * 60)
    
    # MSSQL 資料範圍: 2025-10-08 ~ 2026-01-08
    # 批次覆蓋範圍: 2025-10-08 ~ 2025-10-14
    
    print("MSSQL 資料範圍: 2025-10-08 15:18:55 ~ 2026-01-08 19:59:22")
    print("批次覆蓋範圍: 2025-10-08 15:18:55 ~ 2025-10-14 15:18:55")
    print("缺失範圍: 2025-10-14 15:18:55 ~ 2026-01-08 19:59:22")
    
    # 計算需要多少個批次（假設每個批次 3 天）
    start_missing = datetime(2025, 10, 14, 15, 18, 55)
    end_missing = datetime(2026, 1, 8, 19, 59, 22)
    days_missing = (end_missing - start_missing).days
    batches_needed = (days_missing + 2) // 3  # 每 3 天一個批次
    
    print(f"缺失天數: {days_missing} 天")
    print(f"需要批次數: 約 {batches_needed} 個（每 3 天一批次）")

if __name__ == "__main__":
    main()