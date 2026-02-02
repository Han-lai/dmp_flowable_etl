#!/usr/bin/env python3
"""
透過 ClickHouse JDBC 查詢 MSSQL FlowableTaskStats 表
"""

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
    print("=" * 80)
    print("透過 ClickHouse JDBC 查詢 MSSQL FlowableTaskStats")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    # 1. 查詢 MSSQL FlowableTaskStats 總筆數
    print("\n1. MSSQL FlowableTaskStats 總筆數:")
    try:
        count = client.command("""
            SELECT count(*) FROM jdbc('mssql_master', '
                SELECT * FROM APP_SRV_COMMON.dbo.FlowableTaskStats
            ')
        """)
        print(f"   總筆數: {count:,}")
    except Exception as e:
        print(f"   查詢失敗: {e}")

    # 2. TaskStatus 分布
    print("\n2. MSSQL TaskStatus 分布:")
    try:
        result = client.query("""
            SELECT TaskStatus, cnt FROM jdbc('mssql_master', '
                SELECT TaskStatus, COUNT(*) as cnt
                FROM APP_SRV_COMMON.dbo.FlowableTaskStats
                GROUP BY TaskStatus
            ')
        """)
        for row in result.result_rows:
            print(f"   {row[0]}: {row[1]:,}")
    except Exception as e:
        print(f"   查詢失敗: {e}")

    # 3. TaskBypass 分布
    print("\n3. MSSQL TaskBypass 分布:")
    try:
        result = client.query("""
            SELECT TaskBypass, cnt FROM jdbc('mssql_master', '
                SELECT TaskBypass, COUNT(*) as cnt
                FROM APP_SRV_COMMON.dbo.FlowableTaskStats
                GROUP BY TaskBypass
            ')
        """)
        for row in result.result_rows:
            print(f"   {row[0]}: {row[1]:,}")
    except Exception as e:
        print(f"   查詢失敗: {e}")

    # 4. Plant 分布
    print("\n4. MSSQL Plant 分布:")
    try:
        result = client.query("""
            SELECT Plant, cnt FROM jdbc('mssql_master', '
                SELECT Plant, COUNT(*) as cnt
                FROM APP_SRV_COMMON.dbo.FlowableTaskStats
                GROUP BY Plant
                ORDER BY cnt DESC
            ')
        """)
        for row in result.result_rows:
            print(f"   {row[0]}: {row[1]:,}")
    except Exception as e:
        print(f"   查詢失敗: {e}")

    # 5. 與已同步資料比對
    print("\n" + "=" * 80)
    print("5. 比對 ClickHouse 已同步資料 (bronze.common_flowable_task_stats):")
    
    ch_count = client.command("""
        SELECT count() FROM bronze.common_flowable_task_stats FINAL
    """)
    print(f"   ClickHouse 筆數: {ch_count:,}")

    # 6. 18,343 的可能來源分析
    print("\n" + "=" * 80)
    print("6. 尋找 18,343 筆的查詢條件:")
    
    # 各種條件組合
    queries = [
        ("特定日期 2025-12-25", "TaskCreateDate = '2025-12-25'"),
        ("特定日期 + 排除bypass", "TaskCreateDate = '2025-12-25' AND (TaskBypass != 'Y' OR TaskBypass IS NULL)"),
        ("WJ2 + 特定日期", "Plant = 'WJ2' AND TaskCreateDate = '2025-12-25'"),
        ("V2 全部", "TaskDefinitionKey LIKE 'V2%'"),
        ("V2 排除bypass", "TaskDefinitionKey LIKE 'V2%' AND (TaskBypass != 'Y' OR TaskBypass IS NULL)"),
    ]
    
    target = 18343
    for name, cond in queries:
        try:
            count = client.command(f"""
                SELECT count() FROM bronze.common_flowable_task_stats FINAL
                WHERE {cond}
            """)
            diff = abs(count - target)
            match = "🎯" if diff < 100 else ("✅" if diff < 1000 else "")
            print(f"   {match} {name}: {count:,} (差異: {diff:,})")
        except Exception as e:
            print(f"   {name}: 錯誤 - {e}")

    print("\n" + "=" * 80)
    client.close()

if __name__ == "__main__":
    main()
