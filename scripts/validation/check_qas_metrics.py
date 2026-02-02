import clickhouse_connect
import pandas as pd

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("Connecting to ClickHouse to query MSSQL via JDBC...")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("\n查詢條件: Plant='WJ2', Factory='NBU', Line='E4'")
    print("日期: 2025-12-25, 2025-12-26, 2025-12-27")
    print("邏輯: 模擬 QAS (Start OR Claim OR End)")
    
    # 使用 JDBC 查詢 MSSQL
    # 注意: 直接在 ClickHouse 這裡做邏輯處理，但資料來源是 MSSQL
    query = """
    WITH raw_mssql AS (
        SELECT * FROM jdbc('mssql_master', '
            SELECT 
                TaskDefinitionKey, 
                MoNumber, 
                TaskStatus,
                TaskBypass,
                TaskCreateDate, 
                TaskClaimDate, 
                TaskEndDate
            FROM APP_SRV_COMMON.dbo.FlowableTaskStats
            WHERE Plant = ''WJ2'' 
              AND Factory = ''NBU'' 
              AND Line = ''E4''
        ')
    )
    SELECT 
        snapshot_date,
        vx_type,
        count() as total,
        countIf(status = 'DONE') as done
    FROM (
        SELECT 
            -- 展開日期 (Start, Claim, End)
            arrayJoin(arrayDistinct(arrayFilter(x -> toDate(x) IS NOT NULL, [
                toDate(TaskCreateDate), 
                toDate(TaskClaimDate), 
                toDate(TaskEndDate)
            ]))) as snapshot_date,
            
            -- Vx 邏輯
            CASE 
                WHEN MoNumber LIKE '315%' THEN 'V1'
                WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
                     OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%' THEN 'V1'
                WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
                WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
                WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
                ELSE 'Other'
            END AS vx_type,
            
            TaskStatus as status,
            
            -- 排除邏輯 (Bypass = Y)
            coalesce(TaskBypass, 'N') as bypass
            
        FROM raw_mssql
    )
    WHERE snapshot_date IN ('2025-12-25', '2025-12-26', '2025-12-27')
      AND bypass != 'Y'
    GROUP BY snapshot_date, vx_type
    ORDER BY snapshot_date, vx_type
    """
    
    try:
        result = client.query(query)
        print("\n=== MSSQL (via JDBC) 查詢結果 ===")
        if result.result_rows:
            print("| Date | Vx | Total | DONE |")
            print("|------|----|------:|-----:|")
            for row in result.result_rows:
                print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
        else:
            print("查無資料")
            
    except Exception as e:
        print(f"查詢錯誤: {e}")
        print("可能原因: MSSQL 欄位名稱不符或連線問題")

if __name__ == "__main__":
    main()
