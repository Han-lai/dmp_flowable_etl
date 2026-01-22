#!/usr/bin/env python3
"""
檢查 Bronze 層表結構
"""

import clickhouse_connect

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default',
            database='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def check_bronze_tables(client):
    """檢查 Bronze 層表結構"""
    
    print("🔍 檢查 Bronze 層表")
    query = "SHOW TABLES FROM bronze"
    
    try:
        result = client.query(query)
        tables = [row[0] for row in result.result_rows]
        print(f"📊 Bronze 層表列表:")
        for table in tables:
            print(f"  - {table}")
    except Exception as e:
        print(f"❌ 查詢失敗: {e}")
        return
    
    # 檢查任務相關表的結構
    task_tables = [t for t in tables if 'task' in t.lower() or 'hi_task' in t.lower()]
    
    for table in task_tables:
        print(f"\n🔍 檢查表 bronze.{table} 結構:")
        try:
            schema_query = f"DESCRIBE bronze.{table}"
            result = client.query(schema_query)
            print("欄位名稱 | 資料型別")
            print("-" * 40)
            for row in result.result_rows:
                print(f"{row[0]:20} | {row[1]}")
        except Exception as e:
            print(f"❌ 無法查詢表結構: {e}")

def main():
    """主執行函數"""
    print("🔍 Bronze 層表結構檢查")
    print("="*50)
    
    client = get_clickhouse_client()
    if client is None:
        return
    
    check_bronze_tables(client)
    
    try:
        client.close()
    except:
        pass

if __name__ == "__main__":
    main()