#!/usr/bin/env python3
"""
調試為什麼 MSSQL 查詢中缺少 199% 工單號任務
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

def debug_199_missing(conn, test_date='2025-12-30'):
    """調試 199% 工單號任務缺失問題"""
    
    print(f"🔍 Step 1: 檢查 199% 工單號任務是否存在於 MSSQL")
    query1 = f"""
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
            END AS task_status,
            
            -- 日期匹配檢查
            CASE 
                WHEN CONVERT(DATE, hti.START_TIME_) = '{test_date}' THEN 'START_MATCH'
                WHEN CONVERT(DATE, hti.CLAIM_TIME_) = '{test_date}' THEN 'CLAIM_MATCH'
                WHEN CONVERT(DATE, hti.END_TIME_) = '{test_date}' THEN 'END_MATCH'
                ELSE 'NO_MATCH'
            END AS date_match_type
            
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST hti
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_PROCINST hpi ON hti.PROC_INST_ID_ = hpi.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hti.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hti.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hti.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber ON hti.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ AND var_moNumber.NAME_ = 'moNumber'
        WHERE var_moNumber.TEXT_ IN ('1990000003', '1990010003')
    )
    SELECT 
        mo_number, task_definition_key, task_status, vx_type,
        plant, factory, line,
        START_TIME_, CLAIM_TIME_, END_TIME_, ASSIGNEE_,
        date_match_type
    FROM task_with_dimensions
    ORDER BY mo_number, START_TIME_
    """
    
    try:
        df1 = pd.read_sql(query1, conn)
        print(f"📊 MSSQL 中的 199% 工單號任務 ({len(df1)} 筆):")
        print(df1.to_string(index=False))
        
        if len(df1) > 0:
            print(f"\n📊 維度分佈:")
            dimension_stats = df1.groupby(['plant', 'factory', 'line']).size()
            for (plant, factory, line), count in dimension_stats.items():
                print(f"  {plant}/{factory}/{line}: {count} 個任務")
            
            print(f"\n📅 日期匹配分佈:")
            date_stats = df1['date_match_type'].value_counts()
            for date_type, count in date_stats.items():
                print(f"  {date_type}: {count} 個任務")
        
    except Exception as e:
        print(f"❌ Step 1 失敗: {e}")
        return
    
    print(f"\n🔍 Step 2: 檢查為什麼這些任務沒有被包含在原始查詢中")
    query2 = f"""
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
            
            -- 檢查各種篩選條件
            CASE WHEN (
                CONVERT(DATE, hti.START_TIME_) = '{test_date}'
                OR CONVERT(DATE, hti.CLAIM_TIME_) = '{test_date}'
                OR CONVERT(DATE, hti.END_TIME_) = '{test_date}'
            ) THEN 1 ELSE 0 END as date_filter_pass,
            
            CASE WHEN var_plant.TEXT_ = 'WJ2' THEN 1 ELSE 0 END as plant_filter_pass,
            CASE WHEN var_factory.TEXT_ = 'NBU' THEN 1 ELSE 0 END as factory_filter_pass,
            CASE WHEN var_lineName.TEXT_ = 'E5' THEN 1 ELSE 0 END as line_filter_pass
            
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST hti
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_PROCINST hpi ON hti.PROC_INST_ID_ = hpi.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hti.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hti.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hti.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber ON hti.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ AND var_moNumber.NAME_ = 'moNumber'
        WHERE var_moNumber.TEXT_ IN ('1990000003', '1990010003')
    )
    SELECT 
        mo_number, vx_type, plant, factory, line,
        date_filter_pass, plant_filter_pass, factory_filter_pass, line_filter_pass,
        CASE WHEN date_filter_pass = 1 AND plant_filter_pass = 1 AND factory_filter_pass = 1 AND line_filter_pass = 1 AND vx_type = 'V1' THEN 1 ELSE 0 END as should_be_included
    FROM task_with_dimensions
    ORDER BY mo_number
    """
    
    try:
        df2 = pd.read_sql(query2, conn)
        print(f"📊 篩選條件檢查 ({len(df2)} 筆):")
        print(df2.to_string(index=False))
        
        should_be_included = df2[df2['should_be_included'] == 1]
        print(f"\n📊 應該被包含但被排除的任務: {len(should_be_included)} 筆")
        if len(should_be_included) > 0:
            print(should_be_included.to_string(index=False))
        
    except Exception as e:
        print(f"❌ Step 2 失敗: {e}")

def main():
    """主執行函數"""
    print("🔍 調試 MSSQL 中 199% 工單號任務缺失問題")
    print("="*60)
    
    conn = get_mssql_connection()
    if conn is None:
        print("❌ MSSQL 連線失敗")
        return
    
    debug_199_missing(conn)
    
    try:
        conn.close()
    except:
        pass

if __name__ == "__main__":
    main()