#!/usr/bin/env python3
"""
比較 ClickHouse 和 MSSQL 的任務狀態邏輯
"""

import clickhouse_connect
import pyodbc
import pandas as pd

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default',
            database='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

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

def compare_task_status(ch_client, ms_conn, test_date='2025-12-30'):
    """比較任務狀態邏輯"""
    
    print(f"🔍 比較 ClickHouse 和 MSSQL 的任務狀態邏輯")
    
    # ClickHouse 查詢
    ch_query = f"""
    SELECT 
        mo_number, task_definition_key, task_status,
        task_create_time, task_claim_time, task_end_time,
        -- 顯示狀態判斷邏輯
        task_end_time IS NOT NULL as has_end_time,
        task_claim_time IS NOT NULL as has_claim_time,
        task_create_time IS NOT NULL as has_create_time
    FROM silver.mv_fact_task_vx_attribution
    WHERE (
        toDate(task_create_time) = '{test_date}'
        OR toDate(task_claim_time) = '{test_date}'
        OR toDate(task_end_time) = '{test_date}'
    )
      AND plant = 'WJ2'
      AND factory = 'NBU' 
      AND line = 'E5'
      AND vx_type = 'V1'
    ORDER BY mo_number, task_create_time
    """
    
    try:
        ch_result = ch_client.query(ch_query)
        ch_df = pd.DataFrame(ch_result.result_rows, columns=ch_result.column_names)
        print(f"\n📊 ClickHouse 任務狀態詳情 ({len(ch_df)} 筆):")
        print(ch_df.to_string(index=False))
    except Exception as e:
        print(f"❌ ClickHouse 查詢失敗: {e}")
        ch_df = None
    
    # MSSQL 查詢
    ms_query = f"""
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
            
            -- 任務狀態邏輯
            CASE 
                WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NULL THEN 'TODO'
                ELSE 'UNKNOWN'
            END AS task_status,
            
            -- 顯示狀態判斷邏輯
            CASE WHEN hti.END_TIME_ IS NOT NULL THEN 1 ELSE 0 END as has_end_time,
            CASE WHEN hti.ASSIGNEE_ IS NOT NULL THEN 1 ELSE 0 END as has_assignee,
            CASE WHEN hti.CLAIM_TIME_ IS NOT NULL THEN 1 ELSE 0 END as has_claim_time
            
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST hti
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_PROCINST hpi ON hti.PROC_INST_ID_ = hpi.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hti.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hti.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hti.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber ON hti.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ AND var_moNumber.NAME_ = 'moNumber'
        WHERE (
            CONVERT(DATE, hti.START_TIME_) = '{test_date}'
            OR CONVERT(DATE, hti.CLAIM_TIME_) = '{test_date}'
            OR CONVERT(DATE, hti.END_TIME_) = '{test_date}'
        )
    )
    SELECT 
        mo_number, task_definition_key, task_status,
        START_TIME_, CLAIM_TIME_, END_TIME_, ASSIGNEE_,
        has_end_time, has_assignee, has_claim_time
    FROM task_with_dimensions
    WHERE vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
    ORDER BY mo_number, START_TIME_
    """
    
    try:
        ms_df = pd.read_sql(ms_query, ms_conn)
        print(f"\n📊 MSSQL 任務狀態詳情 ({len(ms_df)} 筆):")
        print(ms_df.to_string(index=False))
    except Exception as e:
        print(f"❌ MSSQL 查詢失敗: {e}")
        ms_df = None
    
    # 比較狀態分佈
    if ch_df is not None and ms_df is not None:
        print(f"\n📊 狀態分佈比較:")
        print(f"ClickHouse 狀態分佈:")
        ch_status = ch_df['task_status'].value_counts()
        for status, count in ch_status.items():
            print(f"  {status}: {count}")
        
        print(f"\nMSSQL 狀態分佈:")
        ms_status = ms_df['task_status'].value_counts()
        for status, count in ms_status.items():
            print(f"  {status}: {count}")

def main():
    """主執行函數"""
    print("🔍 比較任務狀態邏輯")
    print("="*50)
    
    ch_client = get_clickhouse_client()
    ms_conn = get_mssql_connection()
    
    if ch_client is None or ms_conn is None:
        print("❌ 連線失敗")
        return
    
    compare_task_status(ch_client, ms_conn)
    
    try:
        ch_client.close()
        ms_conn.close()
    except:
        pass

if __name__ == "__main__":
    main()