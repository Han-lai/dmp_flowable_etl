#!/usr/bin/env python3
"""
檢查 Bronze 層表格狀態
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
    
    # 檢查 bronze 資料庫中的表
    tables_sql = """
    SELECT name, engine, total_rows, total_bytes
    FROM system.tables 
    WHERE database = 'bronze' 
    ORDER BY name
    """
    
    result = client.query(tables_sql)
    
    print("📊 Bronze 層表格狀態:")
    print("-" * 80)
    print(f"{'表名':<40} {'引擎':<20} {'筆數':<12} {'大小'}")
    print("-" * 80)
    
    for row in result.result_rows:
        name, engine, total_rows, total_bytes = row
        size_mb = total_bytes / 1024 / 1024 if total_bytes else 0
        print(f"{name:<40} {engine:<20} {total_rows:<12,} {size_mb:.2f} MB")
    
    print("-" * 80)
    print(f"總計: {len(result.result_rows)} 個表")
    
    # 特別檢查批次同步相關的表
    batch_tables = [
        'bpm_act_hi_procinst',
        'bpm_act_hi_taskinst', 
        'bpm_act_hi_identitylink',
        'bpm_act_hi_varinst'
    ]
    
    print(f"\n🔍 批次同步相關表格檢查:")
    print("-" * 60)
    
    for table in batch_tables:
        exists = client.command(f"EXISTS TABLE bronze.{table}")
        if exists:
            count = client.command(f"SELECT count(*) FROM bronze.{table}")
            print(f"✅ {table:<30} {count:,} 筆")
        else:
            print(f"❌ {table:<30} 不存在")

if __name__ == "__main__":
    main()