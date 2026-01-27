#!/usr/bin/env python3
"""
MSSQL 日期分布對照查詢
使用與 ClickHouse 相同的時間欄位和條件
"""
import pyodbc
from datetime import datetime

# MSSQL 連接設定
MSSQL_SERVER = "REDACTED_IP"
MSSQL_DATABASE = "DMP_FLOWABLE"
MSSQL_USERNAME = "sa"
MSSQL_PASSWORD = "Aa123456"

def query_mssql(sql, description=""):
    """查詢 MSSQL"""
    try:
        conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={MSSQL_SERVER};DATABASE={MSSQL_DATABASE};UID={MSSQL_USERNAME};PWD={MSSQL_PASSWORD}"
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        print(f"\n🔍 {description}")
        print("SQL:", sql)
        print("-" * 60)
        
        cursor.execute(sql)
        results = cursor.fetchall()
        
        conn.close()
        return results
        
    except Exception as e:
        print(f"❌ MSSQL 查詢錯誤: {e}")
        return None

def main():
    """MSSQL 日期分布檢查"""
    print("=" * 80)
    print("MSSQL 日期分布對照查詢")
    print("條件: V1 + WJ2 + NBU + E5")
    print("=" * 80)
    
    # 1. 使用 task_create_time (對應 ClickHouse)
    sql_create_time = """
    SELECT 
        CAST(t.CREATE_TIME_ AS DATE) as create_date,
        COUNT(*) as task_count,
        SUM(CASE WHEN t.END_TIME_ IS NOT NULL THEN 1 ELSE 0 END) as done_count
    FROM [dmp_flowable].[dbo].[ACT_HI_TASKINST] t
    INNER JOIN [dmp_flowable].[dbo].[ACT_HI_PROCINST] p ON t.PROC_INST_ID_ = p.ID_
    INNER JOIN [dmp_flowable].[dbo].[DMP_FUNCTION_CONFIG] f ON p.BUSINESS_KEY_ = f.BIZ_EVENT_KEY
    WHERE f.VX_TYPE = 'V1'
      AND f.PLANT = 'WJ2'
      AND f.FACTORY = 'NBU'
      AND f.LINE = 'E5'
      AND t.TASK_DEF_KEY_ NOT LIKE '%bypass%'
      AND f.BIZ_EVENT_KEY NOT LIKE '%test%'
    GROUP BY CAST(t.CREATE_TIME_ AS DATE)
    ORDER BY create_date
    """
    
    results_create = query_mssql(sql_create_time, "MSSQL - 按 CREATE_TIME 分組")
    if results_create:
        print(f"MSSQL CREATE_TIME 共 {len(results_create)} 個日期:")
        for row in results_create:
            date, total, done = row
            print(f"  {date}: 總數={total}, 完成={done}")
    
    # 2. 檢查 12/28 和 12/31 的具體資料
    sql_specific_dates = """
    SELECT 
        CAST(t.CREATE_TIME_ AS DATE) as create_date,
        COUNT(*) as task_count,
        SUM(CASE WHEN t.END_TIME_ IS NOT NULL THEN 1 ELSE 0 END) as done_count
    FROM [dmp_flowable].[dbo].[ACT_HI_TASKINST] t
    INNER JOIN [dmp_flowable].[dbo].[ACT_HI_PROCINST] p ON t.PROC_INST_ID_ = p.ID_
    INNER JOIN [dmp_flowable].[dbo].[DMP_FUNCTION_CONFIG] f ON p.BUSINESS_KEY_ = f.BIZ_EVENT_KEY
    WHERE f.VX_TYPE = 'V1'
      AND f.PLANT = 'WJ2'
      AND f.FACTORY = 'NBU'
      AND f.LINE = 'E5'
      AND t.TASK_DEF_KEY_ NOT LIKE '%bypass%'
      AND f.BIZ_EVENT_KEY NOT LIKE '%test%'
      AND CAST(t.CREATE_TIME_ AS DATE) IN ('2025-12-28', '2025-12-31')
    GROUP BY CAST(t.CREATE_TIME_ AS DATE)
    ORDER BY create_date
    """
    
    results_specific = query_mssql(sql_specific_dates, "MSSQL - 12/28 vs 12/31 對比")
    if results_specific:
        print("MSSQL 特定日期對比:")
        for row in results_specific:
            date, total, done = row
            print(f"  {date}: 總數={total}, 完成={done}")
    
    # 3. 檢查最近 7 天的資料
    sql_recent = """
    SELECT 
        CAST(t.CREATE_TIME_ AS DATE) as create_date,
        COUNT(*) as task_count
    FROM [dmp_flowable].[dbo].[ACT_HI_TASKINST] t
    INNER JOIN [dmp_flowable].[dbo].[ACT_HI_PROCINST] p ON t.PROC_INST_ID_ = p.ID_
    INNER JOIN [dmp_flowable].[dbo].[DMP_FUNCTION_CONFIG] f ON p.BUSINESS_KEY_ = f.BIZ_EVENT_KEY
    WHERE f.VX_TYPE = 'V1'
      AND f.PLANT = 'WJ2'
      AND f.FACTORY = 'NBU'
      AND f.LINE = 'E5'
      AND t.TASK_DEF_KEY_ NOT LIKE '%bypass%'
      AND f.BIZ_EVENT_KEY NOT LIKE '%test%'
      AND t.CREATE_TIME_ >= DATEADD(day, -7, GETDATE())
    GROUP BY CAST(t.CREATE_TIME_ AS DATE)
    ORDER BY create_date DESC
    """
    
    results_recent = query_mssql(sql_recent, "MSSQL - 最近 7 天")
    if results_recent:
        print("MSSQL 最近 7 天:")
        for row in results_recent:
            date, total = row
            print(f"  {date}: {total} 筆")

if __name__ == "__main__":
    main()