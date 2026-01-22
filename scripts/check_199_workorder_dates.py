#!/usr/bin/env python3
"""
檢查 199% 工單號任務的具體日期分佈
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
        
        print("❌ 所有 MSSQL 連線嘗試都失敗")
        return None
        
    except Exception as e:
        print(f"❌ MSSQL 連線失敗: {e}")
        return None

def check_199_workorders(conn):
    """檢查 199% 工單號任務的日期分佈"""
    
    query = """
    WITH task_with_dimensions AS (
        SELECT 
            hti.ID_ as task_id,
            hti.PROC_INST_ID_ as proc_inst_id,
            hti.TASK_DEF_KEY_ as task_definition_key,
            hti.START_TIME_,
            hti.CLAIM_TIME_,
            hti.END_TIME_,
            hti.ASSIGNEE_,
            hpi.BUSINESS_KEY_,
            
            -- 從 ACT_HI_VARINST 取得維度資訊
            var_plant.TEXT_ as plant,
            var_factory.TEXT_ as factory,
            var_lineName.TEXT_ as line,
            var_moNumber.TEXT_ as mo_number,
            
            -- V1/V3 歸屬邏輯
            CASE 
                WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                WHEN var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                WHEN var_moNumber.TEXT_ LIKE '196%' 
                     OR var_moNumber.TEXT_ LIKE '199%' 
                     OR var_moNumber.TEXT_ LIKE '200%'
                     OR var_moNumber.TEXT_ LIKE '210%' 
                     OR var_moNumber.TEXT_ LIKE '212%' 
                     OR var_moNumber.TEXT_ LIKE '213%'
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
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hti.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hti.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hti.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber ON hti.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ AND var_moNumber.NAME_ = 'moNumber'
        WHERE var_moNumber.TEXT_ IN ('1990000003', '1990010003')
          AND var_plant.TEXT_ = 'WJ2'
          AND var_factory.TEXT_ = 'NBU'
          AND var_lineName.TEXT_ = 'E5'
    )
    SELECT 
        mo_number, task_definition_key, task_status,
        START_TIME_, CLAIM_TIME_, END_TIME_,
        CONVERT(DATE, START_TIME_) as start_date,
        CONVERT(DATE, CLAIM_TIME_) as claim_date,
        CONVERT(DATE, END_TIME_) as end_date,
        CASE 
            WHEN CONVERT(DATE, START_TIME_) = '2025-12-30' THEN 'START_MATCH'
            WHEN CONVERT(DATE, CLAIM_TIME_) = '2025-12-30' THEN 'CLAIM_MATCH'
            WHEN CONVERT(DATE, END_TIME_) = '2025-12-30' THEN 'END_MATCH'
            ELSE 'NO_MATCH'
        END as date_match_2025_12_30
    FROM task_with_dimensions
    ORDER BY mo_number, START_TIME_
    """
    
    try:
        df = pd.read_sql(query, conn)
        print(f"📊 199% 工單號任務詳細資料 ({len(df)} 筆):")
        print(df.to_string(index=False))
        
        if len(df) > 0:
            print(f"\n📅 日期匹配分析:")
            date_match_stats = df['date_match_2025_12_30'].value_counts()
            for match_type, count in date_match_stats.items():
                print(f"  {match_type}: {count} 個任務")
        
        return df
    except Exception as e:
        print(f"❌ 查詢失敗: {e}")
        return None

def main():
    """主執行函數"""
    print("🔍 檢查 199% 工單號任務的日期分佈")
    print("="*50)
    
    conn = get_mssql_connection()
    if conn is None:
        print("❌ MSSQL 連線失敗")
        return
    
    check_199_workorders(conn)
    
    try:
        conn.close()
    except:
        pass

if __name__ == "__main__":
    main()