#!/usr/bin/env python3
"""
調試 MSSQL 查詢，分步驟檢查資料
"""

import pyodbc
import pandas as pd

def get_mssql_connection():
    """建立 MSSQL 連線"""
    try:
        connection_strings = [
            "DRIVER={ODBC Driver 17 for SQL Server};SERVER=twtpesqldv2.delta.corp,1433;DATABASE=APP_SRV_BPM;UID=DMP_APP_SRV;PWD=APP@DB#01;",
            "DRIVER={SQL Server};SERVER=twtpesqldv2.delta.corp,1433;DATABASE=APP_SRV_BPM;UID=DMP_APP_SRV;PWD=APP@DB#01;",
            "DRIVER={ODBC Driver 18 for SQL Server};SERVER=twtpesqldv2.delta.corp,1433;DATABASE=APP_SRV_BPM;UID=DMP_APP_SRV;PWD=APP@DB#01;TrustServerCertificate=yes;"
        ]
        
        for conn_str in connection_strings:
            try:
                conn = pyodbc.connect(conn_str, timeout=30)
                print(f"✅ MSSQL 連線成功")
                return conn
            except Exception as e:
                continue
        return None
    except Exception as e:
        print(f"❌ MSSQL 連線失敗: {e}")
        return None

def debug_step_by_step(conn, test_date='2025-12-30'):
    """分步驟調試查詢"""
    
    print(f"\n🔍 Step 1: 檢查 {test_date} 的任務總數")
    query1 = f"""
    SELECT COUNT(*) as task_count
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST hti
    WHERE (
        CONVERT(DATE, hti.START_TIME_) = '{test_date}'
        OR CONVERT(DATE, hti.CLAIM_TIME_) = '{test_date}'
        OR CONVERT(DATE, hti.END_TIME_) = '{test_date}'
    )
    """
    
    try:
        df1 = pd.read_sql(query1, conn)
        print(f"📊 {test_date} 總任務數: {df1.iloc[0]['task_count']}")
    except Exception as e:
        print(f"❌ Step 1 失敗: {e}")
        return
    
    print(f"\n🔍 Step 2: 檢查包含 WJ2, NBU, E5 的任務")
    query2 = f"""
    SELECT COUNT(*) as task_count
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST hti
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_PROCINST hpi ON hti.PROC_INST_ID_ = hpi.PROC_INST_ID_
    WHERE (
        CONVERT(DATE, hti.START_TIME_) = '{test_date}'
        OR CONVERT(DATE, hti.CLAIM_TIME_) = '{test_date}'
        OR CONVERT(DATE, hti.END_TIME_) = '{test_date}'
    )
    AND hpi.BUSINESS_KEY_ LIKE '%WJ2%'
    AND hpi.BUSINESS_KEY_ LIKE '%NBU%' 
    AND hpi.BUSINESS_KEY_ LIKE '%E5%'
    """
    
    try:
        df2 = pd.read_sql(query2, conn)
        print(f"📊 WJ2+NBU+E5 任務數: {df2.iloc[0]['task_count']}")
    except Exception as e:
        print(f"❌ Step 2 失敗: {e}")
        return
    
    print(f"\n🔍 Step 3: 檢查 BUSINESS_KEY 樣本")
    query3 = f"""
    SELECT TOP 10 hpi.BUSINESS_KEY_, hti.TASK_DEF_KEY_
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST hti
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_PROCINST hpi ON hti.PROC_INST_ID_ = hpi.PROC_INST_ID_
    WHERE (
        CONVERT(DATE, hti.START_TIME_) = '{test_date}'
        OR CONVERT(DATE, hti.CLAIM_TIME_) = '{test_date}'
        OR CONVERT(DATE, hti.END_TIME_) = '{test_date}'
    )
    AND (hpi.BUSINESS_KEY_ LIKE '%WJ2%' OR hpi.BUSINESS_KEY_ LIKE '%NBU%' OR hpi.BUSINESS_KEY_ LIKE '%E5%')
    """
    
    try:
        df3 = pd.read_sql(query3, conn)
        print(f"📊 BUSINESS_KEY 樣本:")
        print(df3.to_string(index=False))
    except Exception as e:
        print(f"❌ Step 3 失敗: {e}")
        return
    
    print(f"\n🔍 Step 4: 檢查 V1 任務")
    query4 = f"""
    SELECT 
        hti.TASK_DEF_KEY_,
        hpi.BUSINESS_KEY_,
        COUNT(*) as task_count
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST hti
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_PROCINST hpi ON hti.PROC_INST_ID_ = hpi.PROC_INST_ID_
    WHERE (
        CONVERT(DATE, hti.START_TIME_) = '{test_date}'
        OR CONVERT(DATE, hti.CLAIM_TIME_) = '{test_date}'
        OR CONVERT(DATE, hti.END_TIME_) = '{test_date}'
    )
    AND hti.TASK_DEF_KEY_ LIKE 'V%'
    AND (hpi.BUSINESS_KEY_ LIKE '%WJ2%' OR hpi.BUSINESS_KEY_ LIKE '%NBU%' OR hpi.BUSINESS_KEY_ LIKE '%E5%')
    GROUP BY hti.TASK_DEF_KEY_, hpi.BUSINESS_KEY_
    ORDER BY task_count DESC
    """
    
    try:
        df4 = pd.read_sql(query4, conn)
        print(f"📊 V* 任務分布:")
        print(df4.to_string(index=False))
    except Exception as e:
        print(f"❌ Step 4 失敗: {e}")
        return

def main():
    """主執行函數"""
    print("🔍 MSSQL 查詢調試")
    print("="*50)
    
    conn = get_mssql_connection()
    if conn is None:
        print("❌ 無法連線到 MSSQL")
        return
    
    debug_step_by_step(conn)
    
    try:
        conn.close()
    except:
        pass

if __name__ == "__main__":
    main()