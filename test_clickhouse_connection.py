#!/usr/bin/env python3
"""
測試 ClickHouse 連線
"""

import clickhouse_connect

def test_connection():
    try:
        # 建立連線
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default',
            database='default'
        )
        
        # 測試基本查詢
        version = client.command('SELECT version()')
        print(f"✅ ClickHouse 連線成功")
        print(f"版本: {version}")
        
        # 檢查現有資料庫
        databases = client.query('SHOW DATABASES').result_rows
        print(f"現有資料庫: {[db[0] for db in databases]}")
        
        # 檢查是否有 bronze, silver, gold 資料庫
        db_names = [db[0] for db in databases]
        for db in ['bronze', 'silver', 'gold']:
            if db in db_names:
                print(f"✅ {db} 資料庫已存在")
            else:
                print(f"❌ {db} 資料庫不存在")
        
        return True
        
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return False

if __name__ == "__main__":
    test_connection()