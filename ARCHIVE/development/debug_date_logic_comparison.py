#!/usr/bin/env python3
"""
調試日期邏輯差異，比較 ClickHouse 和 MSSQL 的日期篩選結果
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

def debug_clickhouse_detailed(client, test_date='2025-12-30'):
    """詳細調試 ClickHouse 資料"""
    
    print(f"\n🔍 ClickHouse: 檢查 Silver 層具體任務資料")
    query = f"""
    SELECT 
        vx_type, vx_subtype, plant, factory, line,
        task_definition_key, task_status, mo_number,
        task_create_time, task_claim_time, task_end_time,
        COUNT(*) as task_count
    FROM silver.mv_fact_task_vx_attribution
    WHERE toDate(task_create_time) = '{test_date}'
      AND plant = 'WJ2'
      AND factory = 'NBU' 
      AND line = 'E5'
      AND vx_type = 'V1'
    GROUP BY vx_type, vx_subtype, plant, factory, line, task_definition_key, task_status, mo_number, task_create_time, task_claim_time, task_end_time
    ORDER BY mo_number, task_create_time
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print(f"📊 ClickHouse Silver 層詳細資料 ({len(df)} 筆):")
        print(df.to_string(index=False))
        
        # 統計工單號分佈
        if len(df) > 0:
            print(f"\n📈 ClickHouse 工單號分佈:")
            mo_stats = df.groupby('mo_number')['task_count'].sum().sort_values(ascending=False)
            for mo, count in mo_stats.items():
                print(f"  {mo}: {count} 個任務")
        
        return df
    except Exception as e:
        print(f"❌ ClickHouse 查詢失敗: {e}")
        return None

def debug_mssql_detailed(conn, test_date='2025-12-30'):
    """詳細調試 MSSQL 資料"""
    
    print(f"\n🔍 MSSQL: 檢查具體任務資料和日期邏輯")
    query = f"""
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
                WHEN CONVERT(DATE, hti.START_TIME_) = '{test_date}' THEN 'START_TIME'
                WHEN CONVERT(DATE, hti.CLAIM_TIME_) = '{test_date}' THEN 'CLAIM_TIME'
                WHEN CONVERT(DATE, hti.END_TIME_) = '{test_date}' THEN 'END_TIME'
                ELSE 'NO_MATCH'
            END AS date_match_type,
            
            -- 排除條件
            CASE 
                WHEN hti.TASK_DEF_KEY_ LIKE 'E%' THEN 1
                WHEN hti.TASK_DEF_KEY_ LIKE 'C%' THEN 1
                WHEN var_moNumber.TEXT_ LIKE 'Q%' THEN 1
                WHEN var_moNumber.TEXT_ LIKE 'R%' THEN 1
                WHEN (SELECT LONG_ FROM APP_SRV_BPM.dbo.ACT_HI_VARINST WHERE TASK_ID_ = hti.ID_ AND NAME_ = 'autoComplete') = 1 THEN 1
                ELSE 0
            END AS is_excluded
            
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
        vx_type, plant, factory, line, mo_number,
        task_definition_key, task_status, date_match_type,
        is_excluded,
        START_TIME_, CLAIM_TIME_, END_TIME_,
        COUNT(*) as task_count
    FROM task_with_dimensions
    WHERE vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
    GROUP BY vx_type, plant, factory, line, mo_number, task_definition_key, task_status, date_match_type, is_excluded, START_TIME_, CLAIM_TIME_, END_TIME_
    ORDER BY mo_number, START_TIME_
    """
    
    try:
        df = pd.read_sql(query, conn)
        print(f"📊 MSSQL 詳細資料 ({len(df)} 筆):")
        print(df.to_string(index=False))
        
        # 統計工單號分佈
        if len(df) > 0:
            print(f"\n📈 MSSQL 工單號分佈:")
            mo_stats = df.groupby('mo_number')['task_count'].sum().sort_values(ascending=False)
            for mo, count in mo_stats.items():
                print(f"  {mo}: {count} 個任務")
            
            print(f"\n📅 MSSQL 日期匹配類型分佈:")
            date_stats = df.groupby('date_match_type')['task_count'].sum()
            for date_type, count in date_stats.items():
                print(f"  {date_type}: {count} 個任務")
        
        return df
    except Exception as e:
        print(f"❌ MSSQL 查詢失敗: {e}")
        return None

def compare_date_logic(ch_df, ms_df):
    """比較日期邏輯差異"""
    print(f"\n" + "="*80)
    print("📅 日期邏輯差異分析")
    print("="*80)
    
    if ch_df is None or ms_df is None:
        print("❌ 無法比較，查詢失敗")
        return
    
    print(f"\n🔍 ClickHouse vs MSSQL 工單號比較:")
    
    # ClickHouse 工單號
    ch_mo_numbers = set()
    if len(ch_df) > 0 and 'mo_number' in ch_df.columns:
        ch_mo_numbers = set(ch_df['mo_number'].unique())
    
    # MSSQL 工單號
    ms_mo_numbers = set()
    if len(ms_df) > 0 and 'mo_number' in ms_df.columns:
        ms_mo_numbers = set(ms_df['mo_number'].unique())
    
    print(f"ClickHouse 工單號: {sorted(ch_mo_numbers)}")
    print(f"MSSQL 工單號: {sorted(ms_mo_numbers)}")
    
    # 找出差異
    only_in_ch = ch_mo_numbers - ms_mo_numbers
    only_in_ms = ms_mo_numbers - ch_mo_numbers
    common = ch_mo_numbers & ms_mo_numbers
    
    print(f"\n📊 工單號差異分析:")
    print(f"共同工單號: {sorted(common)}")
    print(f"僅在 ClickHouse: {sorted(only_in_ch)}")
    print(f"僅在 MSSQL: {sorted(only_in_ms)}")
    
    if only_in_ch:
        print(f"\n⚠️ ClickHouse 多出的工單號可能原因:")
        print(f"1. 日期篩選邏輯差異（ClickHouse 使用 task_create_time，MSSQL 使用 START_TIME/CLAIM_TIME/END_TIME）")
        print(f"2. 維度對應邏輯差異（plant/factory/line 識別方式不同）")
        print(f"3. V1 歸屬邏輯差異（315% 規則實作差異）")

def main():
    """主執行函數"""
    print("🔍 日期邏輯差異調試")
    print("="*50)
    
    # 建立連線
    ch_client = get_clickhouse_client()
    ms_conn = get_mssql_connection()
    
    if ch_client is None:
        print("❌ ClickHouse 連線失敗")
        return
    
    if ms_conn is None:
        print("❌ MSSQL 連線失敗")
        return
    
    # 查詢詳細資料
    ch_df = debug_clickhouse_detailed(ch_client)
    ms_df = debug_mssql_detailed(ms_conn)
    
    # 比較差異
    compare_date_logic(ch_df, ms_df)
    
    # 清理連線
    try:
        ch_client.close()
        ms_conn.close()
    except:
        pass

if __name__ == "__main__":
    main()