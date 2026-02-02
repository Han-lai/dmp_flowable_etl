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
    
    # 建構 User 提供的完整 Connection URL
    # 注意: ClickHouse JDBC function 對特殊字符可能敏感，需小心處理
    jdbc_url = "jdbc:sqlserver://WJOAUATDB01S.delta.corp:65000;database=APP_SRV_BPM;user=APP_SRV_BPM;password=APP_SRV_BPM;encrypt=true;trustServerCertificate=true"
    
    print("\n使用明確的連線字串查詢 (Direct Connection):")
    print(f"URL: {jdbc_url.split(';password')[0]}... (hidden)")
    
    print("\n查詢 ACT_HI_TASKINST_0108 總筆數:")
    
    query = f"""
    SELECT * FROM jdbc('{jdbc_url}', '
        SELECT count(*) as cnt
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108
    ')
    """
    
    try:
        result = client.query(query)
        # 如果成功，會返回一行
        count = result.result_rows[0][0]
        print(f"✅ Source Count (Direct): {count:,}")
        
    except Exception as e:
        print(f"Direct JDBC Error: {e}")
        print("ClickHouse 可能禁止 Ad-hoc JDBC 連線，或者驅動程式配置限制。")
        
        # 如果直接連線失敗，我們比較一下 mssql_master 的定義 (如果看得到)
        # 通常無法直接看，但我們可以比較 mssql_master 是否也是連到這個 DB
        pass

if __name__ == "__main__":
    main()
