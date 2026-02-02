import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("Connecting to ClickHouse...")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("\n查詢 MSSQL (APP_SRV_BPM) 中的所有表名，尋找 0108 結尾:")
    
    # 使用 INFORMATION_SCHEMA 查詢
    query = """
    SELECT * FROM jdbc('mssql_master', '
        SELECT TABLE_NAME 
        FROM APP_SRV_BPM.INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME LIKE ''%0108%''
        ORDER BY TABLE_NAME
    ')
    """
    
    try:
        result = client.query(query)
        if result.result_rows:
            print(f"找到 {len(result.result_rows)} 張表:")
            for row in result.result_rows:
                print(f" - {row[0]}")
        else:
            print("❌ 未找到包含 '0108' 的表")
            
    except Exception as e:
        print(f"查詢錯誤: {e}")
        
    # 同時檢查 Stats 表是否也有後綴
    print("\n檢查 APP_SRV_COMMON 中的表:")
    query_common = """
    SELECT * FROM jdbc('mssql_master', '
        SELECT TABLE_NAME 
        FROM APP_SRV_COMMON.INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME LIKE ''%FlowableTaskStats%''
        ORDER BY TABLE_NAME
    ')
    """
    try:
        result = client.query(query_common)
        for row in result.result_rows:
            print(f" - {row[0]}")
    except:
        pass

if __name__ == "__main__":
    main()
