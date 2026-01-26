#!/usr/bin/env python3
"""
調試 MSSQL 中的 V3 任務和 315% 工單號歸屬邏輯
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
                return conn
            except Exception as e:
                continue
        return None
    except Exception as e:
        return None

def debug_v3_tasks(conn, test_date='2025-12-30'):
    """調試 V3 任務和 315% 工單號"""
    
    print(f"\n🔍 Step 1: 檢查 {test_date} 的 V3 任務")
    query1 = f"""
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
    AND hti.TASK_DEF_KEY_ LIKE 'V3%'
    GROUP BY hti.TASK_DEF_KEY_, hpi.BUSINESS_KEY_
    ORDER BY task_count DESC
    """
    
    try:
        df1 = pd.read_sql(query1, conn)
        print(f"📊 V3 任務分布:")
        print(df1.to_string(index=False))
    except Exception as e:
        print(f"❌ Step 1 失敗: {e}")
        return
    
    print(f"\n🔍 Step 2: 檢查 315% 工單號")
    query2 = f"""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        hti.TASK_DEF_KEY_,
        v.varinst_moNumber,
        hpi.BUSINESS_KEY_,
        COUNT(*) as task_count
    FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST hti
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_PROCINST hpi ON hti.PROC_INST_ID_ = hpi.PROC_INST_ID_
    LEFT JOIN varinst_pivoted v ON hti.PROC_INST_ID_ = v.PROC_INST_ID_
    WHERE (
        CONVERT(DATE, hti.START_TIME_) = '{test_date}'
        OR CONVERT(DATE, hti.CLAIM_TIME_) = '{test_date}'
        OR CONVERT(DATE, hti.END_TIME_) = '{test_date}'
    )
    AND v.varinst_moNumber LIKE '315%'
    GROUP BY hti.TASK_DEF_KEY_, v.varinst_moNumber, hpi.BUSINESS_KEY_
    ORDER BY task_count DESC
    """
    
    try:
        df2 = pd.read_sql(query2, conn)
        print(f"📊 315% 工單號任務:")
        print(df2.to_string(index=False))
    except Exception as e:
        print(f"❌ Step 2 失敗: {e}")
        return
    
    print(f"\n🔍 Step 3: 檢查 V3 任務的 V1 歸屬邏輯")
    query3 = f"""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            STRING_AGG(NAME_, ',') AS varinst_name,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'name')
        GROUP BY PROC_INST_ID_
    ),
    task_with_vx AS (
        SELECT 
            hti.ID_ as task_id,
            hti.TASK_DEF_KEY_ as task_definition_key,
            hpi.BUSINESS_KEY_,
            v.varinst_moNumber,
            v.varinst_name,
            
            -- V1/V3 歸屬邏輯（修正後）
            CASE 
                WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                -- 315% 工單號歸 V1（修正：使用 LIKE '315%' 涵蓋所有 315 開頭工單號）
                WHEN COALESCE(v.varinst_moNumber, '') LIKE '315%' THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                -- 其他工單號規則
                WHEN COALESCE(v.varinst_moNumber, '') LIKE '196%' 
                     OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
                     OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
                     OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
                     OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
                     OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
                THEN 'V1'
                ELSE COALESCE(SUBSTRING(hti.TASK_DEF_KEY_, 1, 2), 'Unknown')
            END AS vx_type,
            
            -- 任務狀態
            CASE 
                WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NULL THEN 'TODO'
                ELSE 'UNKNOWN'
            END AS task_status
            
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST hti
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_PROCINST hpi ON hti.PROC_INST_ID_ = hpi.PROC_INST_ID_
        LEFT JOIN varinst_pivoted v ON hti.PROC_INST_ID_ = v.PROC_INST_ID_
        WHERE (
            CONVERT(DATE, hti.START_TIME_) = '{test_date}'
            OR CONVERT(DATE, hti.CLAIM_TIME_) = '{test_date}'
            OR CONVERT(DATE, hti.END_TIME_) = '{test_date}'
        )
        AND (
            hti.TASK_DEF_KEY_ LIKE 'V3%'
            OR v.varinst_moNumber LIKE '315%'
        )
    )
    SELECT 
        task_definition_key,
        varinst_moNumber,
        vx_type,
        task_status,
        BUSINESS_KEY_,
        COUNT(*) as task_count
    FROM task_with_vx
    GROUP BY task_definition_key, varinst_moNumber, vx_type, task_status, BUSINESS_KEY_
    ORDER BY task_count DESC
    """
    
    try:
        df3 = pd.read_sql(query3, conn)
        print(f"📊 V3 任務的 V1 歸屬邏輯結果:")
        print(df3.to_string(index=False))
    except Exception as e:
        print(f"❌ Step 3 失敗: {e}")
        return

def main():
    """主執行函數"""
    print("🔍 MSSQL V3 任務和 315% 工單號調試")
    print("="*50)
    
    conn = get_mssql_connection()
    if conn is None:
        print("❌ 無法連線到 MSSQL")
        return
    
    debug_v3_tasks(conn)
    
    try:
        conn.close()
    except:
        pass

if __name__ == "__main__":
    main()