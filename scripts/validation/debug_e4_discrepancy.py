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
    
    print("\n1. 檢查 ClickHouse 中 E4 的任務樣本 (2025-12-25)")
    query_ch = """
    SELECT 
        task_id, 
        mo_number, 
        line, 
        line_source, 
        task_create_date,
        count() OVER (PARTITION BY task_id) as dup_count
    FROM silver.mv_fact_task_vx FINAL
    WHERE 
        plant = 'WJ2' 
        AND factory = 'NBU' 
        AND line = 'E4'
        AND task_create_date = '2025-12-25'
    ORDER BY task_id
    LIMIT 10
    """
    result = client.query(query_ch)
    
    ids_to_check = []
    
    if result.result_rows:
        print("\n| TaskID | MO | Line | Source | Date | Dup? |")
        print("|--------|----|------|--------|------|------|")
        for row in result.result_rows:
            print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} |")
            ids_to_check.append(row[0])
    
    print(f"\n2. 在 MSSQL 中查詢這些 TaskID ({len(ids_to_check)} 筆)")
    if ids_to_check:
        # 修正 JDBC 查詢語法，避免過多引號混淆
        ids_str = "', '".join(ids_to_check)
        mssql_sql = f"SELECT ID_, Plant, Factory FROM APP_SRV_COMMON.dbo.FlowableTaskStats WHERE ID_ IN ('{ids_str}')"
        # 注意: 這裡使用了 ID_ 而不是 TaskID，因為 FlowableTaskStats 的主鍵可能是 ID_ (需確認 schema)
        # 如果是 FlowableTaskStats 表，欄位應該是 TaskID。讓我們嘗試抓更基礎的 ACT_HI_TASKINST 表來確認
        
        print("   嘗試查詢 BPM_ACT_HI_TASKINST_0108 (正確的 UAT 表)")
        mssql_sql = f"SELECT ID_, PROC_INST_ID_ FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 WHERE ID_ IN ('{ids_str}')"
        
        try:
            # 簡化：直接打印生成的 SQL 供檢查
            print(f"   執行 SQL: {mssql_sql[:100]}...")
            
            # 使用更安全的參數傳遞方式或確保字串轉義正確
            safe_sql = mssql_sql.replace("'", "''")
            query_mssql = f"SELECT * FROM jdbc('mssql_master', '{safe_sql}')"
            
            mssql_res = client.query(query_mssql)
            if mssql_res.result_rows:
                print("\n| ID_ | PROC_INST_ID_ |")
                print("|-----|---------------|")
                for row in mssql_res.result_rows:
                    print(f"| {row[0]} | {row[1]} |")
            else:
                print("❌ MSSQL 中查無這些 ID_")
                
        except Exception as e:
            print(f"MSSQL 查詢失敗: {e}")

if __name__ == "__main__":
    main()
