#!/usr/bin/env python3
"""
檢查目前 bronze._sync_watermark 的狀態
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
    
    # 檢查 watermark 表是否存在
    exists = client.command("EXISTS TABLE bronze._sync_watermark")
    
    if not exists:
        print("❌ bronze._sync_watermark 表不存在")
        return
    
    print("✅ bronze._sync_watermark 表存在")
    
    # 查詢所有 watermark 記錄
    sql = """
    SELECT table_name, last_sync_time, sync_time, row_count
    FROM bronze._sync_watermark FINAL
    ORDER BY table_name
    """
    
    result = client.query(sql)
    
    if not result.result_rows:
        print("⚠️ 沒有 watermark 記錄")
        return
    
    print("\n📊 目前 Watermark 狀態:")
    print("-" * 80)
    print(f"{'表名':<40} {'最後同步時間':<20} {'記錄筆數':<10}")
    print("-" * 80)
    
    for row in result.result_rows:
        table_name, last_sync_time, sync_time, row_count = row
        print(f"{table_name:<40} {str(last_sync_time):<20} {row_count:<10,}")
    
    print("-" * 80)

if __name__ == "__main__":
    main()