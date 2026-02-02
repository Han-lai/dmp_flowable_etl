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
    
    print("\n檢查 MSSQL UAT 表格內容 (無日期篩選):")
    
    tables = [
        "APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108",
        # "APP_SRV_BPM.dbo.ACT_HI_VARINST_0108" # 先查主表
    ]
    
    for table in tables:
        print(f"\nTable: {table}")
        
        # 1. 總筆數
        try:
            count_sql = f"SELECT count(*) FROM {table}"
            count = client.command(f"SELECT count(*) FROM jdbc('mssql_master', '{count_sql}')")
            print(f"  總筆數: {count:,}")
        except Exception as e:
            print(f"  Count Error: {e}")
            continue

        if count > 0:
            # 2. 隨機採樣看時間分布
            print("  Top 5 資料 (ID, CreateTime, StartTime):")
            try:
                # MSSQL T-SQL syntax
                top_sql = f"SELECT TOP 5 ID_, CREATE_TIME_, START_TIME_ FROM {table}"
                result = client.query(f"SELECT * FROM jdbc('mssql_master', '{top_sql}')")
                
                print("| ID | CreateTime | StartTime |")
                print("|----|------------|-----------|")
                for row in result.result_rows:
                    print(f"| {row[0]} | {row[1]} | {row[2]} |")
            except Exception as e:
                print(f"  Sample Error: {e}")
                
            # 3. 檢查日期分佈 (如果有資料)
            try:
                print("\n  日期分佈 (Group by Date):")
                # 注意 T-SQL 語法
                date_sql = f"""
                    SELECT cast(START_TIME_ as date) as Dt, count(*) as Cnt 
                    FROM {table} 
                    GROUP BY cast(START_TIME_ as date) 
                    ORDER BY Dt DESC
                """
                dist_res = client.query(f"SELECT * FROM jdbc('mssql_master', '{date_sql}')")
                for row in dist_res.result_rows:
                    print(f"  {row[0]}: {row[1]} 筆")
            except Exception as e:
                print(f"  Date Dist Error: {e}")

if __name__ == "__main__":
    main()
