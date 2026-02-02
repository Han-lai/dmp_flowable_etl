#!/usr/bin/env python3
"""
檢查 ClickHouse 活動會話
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
    
    try:
        # 查詢活動進程
        sessions_sql = """
        SELECT query_id, user, query
        FROM system.processes
        LIMIT 10
        """
        
        result = client.query(sessions_sql)
        
        if result.result_rows:
            print("🔍 活動進程:")
            print("-" * 100)
            print(f"{'Query ID':<40} {'用戶':<10} {'查詢':<40}")
            print("-" * 100)
            
            for row in result.result_rows:
                query_id, user, query = row
                query_short = (query[:37] + "...") if len(query) > 40 else query
                print(f"{query_id:<40} {user:<10} {query_short:<40}")
        else:
            print("✅ 沒有活動進程")
        
        # 查詢進程統計
        session_stats_sql = """
        SELECT 
            COUNT(*) as total_processes
        FROM system.processes
        """
        
        result = client.query(session_stats_sql)
        if result.result_rows:
            total = result.result_rows[0][0]
            print(f"\n📊 進程統計: 總計 {total} 個活動進程")
        
    except Exception as e:
        print(f"❌ 查詢會話失敗: {e}")

if __name__ == "__main__":
    main()