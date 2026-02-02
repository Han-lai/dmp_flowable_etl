import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("Connecting to ClickHouse...")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("\n透過 mssql_master 查詢伺服器資訊:")
    
    query = """
    SELECT * FROM jdbc('mssql_master', '
        SELECT 
            @@SERVERNAME as ServerName,
            DB_NAME() as CurrentDB,
            @@VERSION as Version
    ')
    """
    
    try:
        result = client.query(query)
        if result.result_rows:
            row = result.result_rows[0]
            print(f"✅ 連接到的伺服器: {row[0]}")
            print(f"✅ 當前資料庫:     {row[1]}")
            print(f"ℹ️ 版本資訊:       {row[2].splitlines()[0]}")
        else:
            print("❌ 無法獲取伺服器資訊")
            
    except Exception as e:
        print(f"查詢錯誤: {e}")

if __name__ == "__main__":
    main()
