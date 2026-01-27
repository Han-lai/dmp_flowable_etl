#!/usr/bin/env python3
"""
簡單測試 REFRESHABLE MATERIALIZED VIEW 是否可用
"""
import clickhouse_connect

def test():
    print("測試 REFRESHABLE MATERIALIZED VIEW...")
    
    client = clickhouse_connect.get_client(
        host="REDACTED_IP",
        port=8121,
        username="default",
        password="default"
    )
    
    try:
        # 開啟實驗性功能
        print("開啟實驗性功能...")
        client.command("SET allow_experimental_refreshable_materialized_view = 1")
        
        # 建立測試資料庫
        client.command("CREATE DATABASE IF NOT EXISTS test")
        
        # 建立測試 MV
        print("建立測試 MV...")
        client.command("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS test.simple_mv
        REFRESH EVERY 1 MINUTE
        ENGINE = MergeTree()
        ORDER BY date
        AS SELECT today() as date, count() as cnt FROM system.numbers LIMIT 1
        """)
        
        print("✅ REFRESHABLE MATERIALIZED VIEW 可以使用")
        
        # 清理
        client.command("DROP VIEW IF EXISTS test.simple_mv")
        
    except Exception as e:
        print(f"❌ 無法使用: {e}")

if __name__ == "__main__":
    test()