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
    
    print("\n從 MSSQL 獲取真實存在的 TaskID (2025-12-25, WJ2, NBU, E4)")
    
    # 從 FlowableTaskStats 查詢 (這是 QAS 的基準)
    query = """
    SELECT * FROM jdbc('mssql_master', '
        SELECT TaskID, TaskStatus, TaskCreateDate 
        FROM APP_SRV_COMMON.dbo.FlowableTaskStats 
        WHERE Plant = ''WJ2'' 
          AND Factory = ''NBU'' 
          AND Line = ''E4''
          AND cast(TaskCreateDate as date) = ''2025-12-25''
    ')
    """
    
    try:
        result = client.query(query)
        print(f"\nMSSQL 查詢結果 (筆數: {len(result.result_rows)})")
        if result.result_rows:
            print("| TaskID | Status | Date |")
            print("|--------|--------|------|")
            for row in result.result_rows:
                print(f"| {row[0]} | {row[1]} | {row[2]} |")
        else:
            print("MSSQL 中查無資料")
            
    except Exception as e:
        print(f"查詢錯誤: {e}")

if __name__ == "__main__":
    main()
