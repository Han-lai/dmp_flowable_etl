#!/usr/bin/env python3
"""
檢查 bronze.sync_batch_control 表結構和資料
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
    
    # 檢查表是否存在
    exists = client.command("EXISTS TABLE bronze.sync_batch_control")
    
    if not exists:
        print("❌ bronze.sync_batch_control 表不存在")
        return
    
    print("✅ bronze.sync_batch_control 表存在")
    
    # 查詢表結構
    print("\n📋 表結構:")
    structure_sql = """
    SELECT name, type, comment
    FROM system.columns 
    WHERE database = 'bronze' AND table = 'sync_batch_control'
    ORDER BY position
    """
    
    result = client.query(structure_sql)
    print("-" * 60)
    print(f"{'欄位名':<25} {'類型':<20} {'註解'}")
    print("-" * 60)
    
    for row in result.result_rows:
        name, type_name, comment = row
        print(f"{name:<25} {type_name:<20} {comment or ''}")
    
    # 查詢資料樣本
    print("\n📊 資料樣本 (最新 5 筆):")
    sample_sql = """
    SELECT *
    FROM bronze.sync_batch_control FINAL
    ORDER BY created_at DESC
    LIMIT 5
    """
    
    try:
        result = client.query(sample_sql)
        if result.result_rows:
            # 取得欄位名
            columns = [col[0] for col in client.query("DESCRIBE bronze.sync_batch_control").result_rows]
            
            print("-" * 120)
            print(" | ".join(f"{col:<15}" for col in columns[:6]))  # 只顯示前6個欄位
            print("-" * 120)
            
            for row in result.result_rows:
                print(" | ".join(f"{str(val):<15}" for val in row[:6]))
        else:
            print("⚠️ 表中沒有資料")
    except Exception as e:
        print(f"❌ 查詢資料失敗: {e}")
    
    # 查詢各表的最新批次狀態
    print("\n🔍 各表最新批次狀態:")
    status_sql = """
    SELECT 
        table_name,
        COUNT(*) as total_batches,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_batches,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_batches,
        SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_batches,
        MAX(watermark_end) as latest_watermark
    FROM bronze.sync_batch_control FINAL
    GROUP BY table_name
    ORDER BY table_name
    """
    
    try:
        result = client.query(status_sql)
        if result.result_rows:
            print("-" * 100)
            print(f"{'表名':<30} {'總批次':<8} {'完成':<6} {'失敗':<6} {'執行中':<8} {'最新 Watermark'}")
            print("-" * 100)
            
            for row in result.result_rows:
                table_name, total, completed, failed, running, latest_watermark = row
                print(f"{table_name:<30} {total:<8} {completed:<6} {failed:<6} {running:<8} {str(latest_watermark)}")
        else:
            print("⚠️ 沒有批次記錄")
    except Exception as e:
        print(f"❌ 查詢批次狀態失敗: {e}")

if __name__ == "__main__":
    main()