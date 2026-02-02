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
    
    table = "APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108"
    print(f"\n檢查表: {table}")
    
    # 1. 使用 Query 再次確認總數 (避免 Command 返回值誤解)
    try:
        count_sql = f"SELECT count(*) FROM {table}"
        result = client.query(f"SELECT * FROM jdbc('mssql_master', '{count_sql}')")
        if result.result_rows:
            print(f"✅ 真實總筆數: {result.result_rows[0][0]:,}")
    except Exception as e:
        print(f"Count Error: {e}")

    # 2. 查詢最大與最小時間
    try:
        range_sql = f"SELECT MIN(START_TIME_), MAX(START_TIME_) FROM {table}"
        result = client.query(f"SELECT * FROM jdbc('mssql_master', '{range_sql}')")
        if result.result_rows:
            min_t, max_t = result.result_rows[0]
            print(f"📅 資料時間範圍: {min_t} ~ {max_t}")
            
            # 檢查 12月 是否有資料
            if str(max_t) < '2025-12-01':
                print("⚠️ 警告: 資料似乎只到 11月，不包含 12月！")
    except Exception as e:
        print(f"Range Error: {e}")

    # 3. 專門檢查 2025-12-25
    try:
        specific_sql = f"SELECT count(*) FROM {table} WHERE cast(START_TIME_ as date) = ''2025-12-25''"
        result = client.query(f"SELECT * FROM jdbc('mssql_master', '{specific_sql}')")
        if result.result_rows:
            print(f"🔍 2025-12-25 當日筆數: {result.result_rows[0][0]}")
    except Exception as e:
        print(f"Specific Date Error: {e}")

if __name__ == "__main__":
    main()
