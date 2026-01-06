"""
檢查追蹤欄位的行為
目的：確認追蹤欄位是否能正確反映資料的新增/更新時間
"""

import clickhouse_connect
from datetime import datetime, timedelta

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    print("連線成功\n")
    
    print("=" * 100)
    print("追蹤欄位行為分析")
    print("=" * 100)
    
    # 1. ACT_HI_PROCINST - 檢查 START_TIME_ vs END_TIME_
    print("\n" + "─" * 100)
    print("📋 ACT_HI_PROCINST (流程實例)")
    print("─" * 100)
    
    sql = """
    SELECT * FROM jdbc('mssql_master', '
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN END_TIME_ IS NULL THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN END_TIME_ IS NOT NULL THEN 1 ELSE 0 END) as completed,
            MIN(START_TIME_) as earliest_start,
            MAX(START_TIME_) as latest_start,
            MIN(END_TIME_) as earliest_end,
            MAX(END_TIME_) as latest_end
        FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST
    ')
    """
    result = client.query(sql)
    row = result.result_rows[0]
    print(f"  總筆數: {row[0]:,}")
    print(f"  進行中 (END_TIME_ IS NULL): {row[1]:,}")
    print(f"  已完成 (END_TIME_ IS NOT NULL): {row[2]:,}")
    print(f"  START_TIME_ 範圍: {row[3]} ~ {row[4]}")
    print(f"  END_TIME_ 範圍: {row[5]} ~ {row[6]}")
    print(f"  ⚠️ 結論: 進行中的流程 END_TIME_ 是 NULL，無法用 END_TIME_ 追蹤新建")
    print(f"  💡 建議: 用 START_TIME_ 追蹤新建，用 END_TIME_ 追蹤完成")
    
    # 2. ACT_HI_TASKINST - 檢查 LAST_UPDATED_TIME_
    print("\n" + "─" * 100)
    print("📋 ACT_HI_TASKINST (任務實例)")
    print("─" * 100)
    
    sql = """
    SELECT * FROM jdbc('mssql_master', '
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN LAST_UPDATED_TIME_ IS NULL THEN 1 ELSE 0 END) as null_count,
            MIN(LAST_UPDATED_TIME_) as earliest,
            MAX(LAST_UPDATED_TIME_) as latest,
            MIN(START_TIME_) as earliest_start,
            MAX(START_TIME_) as latest_start
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST
    ')
    """
    result = client.query(sql)
    row = result.result_rows[0]
    print(f"  總筆數: {row[0]:,}")
    print(f"  LAST_UPDATED_TIME_ IS NULL: {row[1]:,}")
    print(f"  LAST_UPDATED_TIME_ 範圍: {row[2]} ~ {row[3]}")
    print(f"  START_TIME_ 範圍: {row[4]} ~ {row[5]}")
    
    # 檢查 LAST_UPDATED_TIME_ 是否 >= START_TIME_
    sql2 = """
    SELECT * FROM jdbc('mssql_master', '
        SELECT COUNT(*) 
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST
        WHERE LAST_UPDATED_TIME_ < START_TIME_
    ')
    """
    result2 = client.query(sql2)
    anomaly = result2.result_rows[0][0]
    print(f"  LAST_UPDATED_TIME_ < START_TIME_ 異常筆數: {anomaly}")
    if row[1] == 0 and anomaly == 0:
        print(f"  ✅ 結論: LAST_UPDATED_TIME_ 可靠，適合做增量同步")
    else:
        print(f"  ⚠️ 結論: 有 NULL 或異常資料，需注意")
    
    # 3. ACT_HI_VARINST - 檢查 LAST_UPDATED_TIME_
    print("\n" + "─" * 100)
    print("📋 ACT_HI_VARINST (變數實例)")
    print("─" * 100)
    
    sql = """
    SELECT * FROM jdbc('mssql_master', '
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN LAST_UPDATED_TIME_ IS NULL THEN 1 ELSE 0 END) as null_count,
            MIN(LAST_UPDATED_TIME_) as earliest,
            MAX(LAST_UPDATED_TIME_) as latest,
            MIN(CREATE_TIME_) as earliest_create,
            MAX(CREATE_TIME_) as latest_create
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
    ')
    """
    result = client.query(sql)
    row = result.result_rows[0]
    print(f"  總筆數: {row[0]:,}")
    print(f"  LAST_UPDATED_TIME_ IS NULL: {row[1]:,}")
    print(f"  LAST_UPDATED_TIME_ 範圍: {row[2]} ~ {row[3]}")
    print(f"  CREATE_TIME_ 範圍: {row[4]} ~ {row[5]}")
    if row[1] == 0:
        print(f"  ✅ 結論: LAST_UPDATED_TIME_ 可靠，適合做增量同步")
    else:
        print(f"  ⚠️ 結論: 有 {row[1]:,} 筆 NULL，需注意")
    
    # 4. ACT_HI_IDENTITYLINK - 檢查 CREATE_TIME_
    print("\n" + "─" * 100)
    print("📋 ACT_HI_IDENTITYLINK (身份連結)")
    print("─" * 100)
    
    sql = """
    SELECT * FROM jdbc('mssql_master', '
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN CREATE_TIME_ IS NULL THEN 1 ELSE 0 END) as null_count,
            MIN(CREATE_TIME_) as earliest,
            MAX(CREATE_TIME_) as latest
        FROM APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK
    ')
    """
    result = client.query(sql)
    row = result.result_rows[0]
    print(f"  總筆數: {row[0]:,}")
    print(f"  CREATE_TIME_ IS NULL: {row[1]:,}")
    print(f"  CREATE_TIME_ 範圍: {row[2]} ~ {row[3]}")
    print(f"  ⚠️ 結論: 只有 CREATE_TIME_，無法追蹤更新（但此表通常只新增不更新）")
    
    # 5. FlowableTaskStats - 檢查 LastUpdatedTime
    print("\n" + "─" * 100)
    print("📋 FlowableTaskStats (任務統計)")
    print("─" * 100)
    
    sql = """
    SELECT * FROM jdbc('mssql_master', '
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN LastUpdatedTime IS NULL THEN 1 ELSE 0 END) as null_count,
            MIN(LastUpdatedTime) as earliest,
            MAX(LastUpdatedTime) as latest
        FROM APP_SRV_COMMON.dbo.FlowableTaskStats
    ')
    """
    result = client.query(sql)
    row = result.result_rows[0]
    print(f"  總筆數: {row[0]:,}")
    print(f"  LastUpdatedTime IS NULL: {row[1]:,}")
    print(f"  LastUpdatedTime 範圍: {row[2]} ~ {row[3]}")
    if row[1] == 0:
        print(f"  ✅ 結論: LastUpdatedTime 可靠，適合做增量同步")
    else:
        print(f"  ⚠️ 結論: 有 {row[1]:,} 筆 NULL")
    
    # 6. 檢查最近 7 天的資料分布（確認追蹤欄位是否持續更新）
    print("\n" + "─" * 100)
    print("📊 最近 7 天資料分布（確認追蹤欄位是否持續更新）")
    print("─" * 100)
    
    tables_to_check = [
        ("ACT_HI_TASKINST", "LAST_UPDATED_TIME_", "APP_SRV_BPM.dbo.ACT_HI_TASKINST"),
        ("ACT_HI_VARINST", "LAST_UPDATED_TIME_", "APP_SRV_BPM.dbo.ACT_HI_VARINST"),
        ("ACT_HI_PROCINST", "START_TIME_", "APP_SRV_BPM.dbo.ACT_HI_PROCINST"),
    ]
    
    for table_name, col, full_table in tables_to_check:
        sql = f"""
        SELECT * FROM jdbc('mssql_master', '
            SELECT 
                CAST({col} AS DATE) as dt,
                COUNT(*) as cnt
            FROM {full_table}
            WHERE {col} >= DATEADD(day, -7, GETDATE())
            GROUP BY CAST({col} AS DATE)
            ORDER BY dt DESC
        ')
        """
        result = client.query(sql)
        print(f"\n  {table_name}.{col}:")
        if result.result_rows:
            for row in result.result_rows:
                print(f"    {row[0]}: {row[1]:,} 筆")
        else:
            print(f"    (最近 7 天無資料)")
    
    # 總結
    print("\n")
    print("=" * 100)
    print("📋 增量同步建議")
    print("=" * 100)
    print("""
┌─────────────────────────┬─────────────────────────┬─────────────────────────────────────┐
│ 表名                    │ 追蹤欄位                │ 建議                                │
├─────────────────────────┼─────────────────────────┼─────────────────────────────────────┤
│ ACT_HI_TASKINST         │ LAST_UPDATED_TIME_      │ ✅ 增量同步（最佳）                 │
│ ACT_HI_VARINST          │ LAST_UPDATED_TIME_      │ ✅ 增量同步（最佳）                 │
│ ACT_HI_PROCINST         │ START_TIME_ + END_TIME_ │ ⚠️ 混合策略（新建用START，完成用END）│
│ ACT_HI_IDENTITYLINK     │ CREATE_TIME_            │ ⚠️ 只能追蹤新建                     │
│ ACT_RE_PROCDEF          │ 無                      │ ❌ 維持全量（資料量小）             │
│ FlowableTaskStats       │ LastUpdatedTime         │ ✅ 增量同步                         │
│ 其他 COMMON 表          │ UpdateDatetime/UpdateTime│ ✅ 增量同步                        │
└─────────────────────────┴─────────────────────────┴─────────────────────────────────────┘
    """)

if __name__ == "__main__":
    main()
