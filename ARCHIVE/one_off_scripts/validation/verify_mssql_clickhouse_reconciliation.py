#!/usr/bin/env python3
"""
MSSQL 與 ClickHouse 對帳驗證腳本
使用五階條件 + 日期篩選，比較兩個資料源的一致性

測試案例：V1 CNE WJ2 NBU E5 + 2025-12-30
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect
import pyodbc
from datetime import datetime
import pandas as pd

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
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
        # 使用提供的連線資訊
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
                print(f"⚠️ 連線字串失敗: {e}")
                continue
        
        print("❌ 所有 MSSQL 連線嘗試都失敗")
        return None
        
    except Exception as e:
        print(f"❌ MSSQL 連線失敗: {e}")
        return None

def query_clickhouse_data(client, test_date='2025-12-30'):
    """查詢 ClickHouse 資料 - 使用與 MSSQL 相同的日期篩選邏輯"""
    query = f"""
    SELECT 
        vx_type,
        plant,
        factory,
        line,
        '{test_date}' as snapshot_date,
        SUM(CASE WHEN task_status = 'TODO' AND is_excluded = 0 THEN 1 ELSE 0 END) as todo_count,
        SUM(CASE WHEN task_status = 'DOING' AND is_excluded = 0 THEN 1 ELSE 0 END) as doing_count,
        SUM(CASE WHEN task_status = 'DONE' AND is_excluded = 0 THEN 1 ELSE 0 END) as done_count,
        SUM(CASE WHEN is_excluded = 0 THEN 1 ELSE 0 END) as total_count,
        SUM(CASE WHEN is_excluded = 1 THEN 1 ELSE 0 END) as excluded_count
    FROM silver.mv_fact_task_vx_attribution
    WHERE (
        toDate(task_create_time) = '{test_date}'
        OR toDate(task_claim_time) = '{test_date}'
        OR toDate(task_end_time) = '{test_date}'
    )
      AND vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU' 
      AND line = 'E5'
    GROUP BY vx_type, plant, factory, line
    ORDER BY vx_type, plant, factory, line
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print(f"✅ ClickHouse 查詢成功，返回 {len(df)} 筆資料")
        return df
    except Exception as e:
        print(f"❌ ClickHouse 查詢失敗: {e}")
        return None

def query_mssql_data(conn, test_date='2025-12-30'):
    """查詢 MSSQL 資料"""
    
    # 使用完整的 L5 指標邏輯，從 ACT_HI_VARINST 中取得維度資訊
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
            
            -- V1/V3 歸屬邏輯（修正後：工單號規則優先）
            CASE 
                -- 工單號規則優先（在任務定義鍵規則之前）
                WHEN var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                WHEN var_moNumber.TEXT_ LIKE '196%' 
                     OR var_moNumber.TEXT_ LIKE '199%' 
                     OR var_moNumber.TEXT_ LIKE '200%'
                     OR var_moNumber.TEXT_ LIKE '210%' 
                     OR var_moNumber.TEXT_ LIKE '212%' 
                     OR var_moNumber.TEXT_ LIKE '213%'
                THEN 'V1'
                -- 任務定義鍵規則其次
                WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                ELSE COALESCE(SUBSTRING(hti.TASK_DEF_KEY_, 1, 2), 'Unknown')
            END AS vx_type,
            
            -- 任務狀態
            CASE 
                WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NULL THEN 'TODO'
                ELSE 'UNKNOWN'
            END AS task_status,
            
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
        vx_type,
        plant,
        factory,
        line,
        '{test_date}' as snapshot_date,
        SUM(CASE WHEN task_status = 'TODO' AND is_excluded = 0 THEN 1 ELSE 0 END) as todo_count,
        SUM(CASE WHEN task_status = 'DOING' AND is_excluded = 0 THEN 1 ELSE 0 END) as doing_count,
        SUM(CASE WHEN task_status = 'DONE' AND is_excluded = 0 THEN 1 ELSE 0 END) as done_count,
        SUM(CASE WHEN is_excluded = 0 THEN 1 ELSE 0 END) as total_count,
        SUM(CASE WHEN is_excluded = 1 THEN 1 ELSE 0 END) as excluded_count
    FROM task_with_dimensions
    WHERE vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
    GROUP BY vx_type, plant, factory, line
    ORDER BY vx_type
    """
    
    try:
        df = pd.read_sql(query, conn)
        print(f"✅ MSSQL 查詢成功，返回 {len(df)} 筆資料")
        return df
    except Exception as e:
        print(f"❌ MSSQL 查詢失敗: {e}")
        return None

def compare_results(clickhouse_df, mssql_df):
    """比較兩個資料源的結果"""
    print("\n" + "="*80)
    print("📊 MSSQL vs ClickHouse 對帳結果比較")
    print("="*80)
    
    if clickhouse_df is None or mssql_df is None:
        print("❌ 無法進行比較，其中一個資料源查詢失敗")
        return False
    
    if len(clickhouse_df) == 0 and len(mssql_df) == 0:
        print("⚠️ 兩個資料源都沒有資料")
        return True
    
    if len(clickhouse_df) == 0:
        print("❌ ClickHouse 沒有資料，但 MSSQL 有資料")
        print("MSSQL 資料:")
        print(mssql_df.to_string(index=False))
        return False
    
    if len(mssql_df) == 0:
        print("❌ MSSQL 沒有資料，但 ClickHouse 有資料")
        print("ClickHouse 資料:")
        print(clickhouse_df.to_string(index=False))
        return False
    
    # 顯示原始資料
    print("\n🔍 ClickHouse 查詢結果:")
    print(clickhouse_df.to_string(index=False))
    
    print("\n🔍 MSSQL 查詢結果:")
    print(mssql_df.to_string(index=False))
    
    # 比較關鍵指標
    print("\n📈 關鍵指標比較:")
    print("-" * 60)
    
    metrics = ['todo_count', 'doing_count', 'done_count', 'total_count', 'excluded_count']
    all_match = True
    
    for metric in metrics:
        ch_value = clickhouse_df[metric].sum() if metric in clickhouse_df.columns else 0
        ms_value = mssql_df[metric].sum() if metric in mssql_df.columns else 0
        
        status = "✅" if ch_value == ms_value else "❌"
        if ch_value != ms_value:
            all_match = False
        
        print(f"{status} {metric:15}: ClickHouse={ch_value:3d}, MSSQL={ms_value:3d}, 差異={ch_value-ms_value:+3d}")
    
    # 計算完成率和執行率
    print("\n📊 計算指標比較:")
    print("-" * 60)
    
    # ClickHouse 計算
    ch_total = clickhouse_df['total_count'].sum() if 'total_count' in clickhouse_df.columns else 0
    ch_done = clickhouse_df['done_count'].sum() if 'done_count' in clickhouse_df.columns else 0
    ch_doing = clickhouse_df['doing_count'].sum() if 'doing_count' in clickhouse_df.columns else 0
    ch_completion_rate = (ch_done / ch_total * 100) if ch_total > 0 else 0
    ch_progress_rate = ((ch_done + ch_doing) / ch_total * 100) if ch_total > 0 else 0
    
    # MSSQL 計算
    ms_total = mssql_df['total_count'].sum() if 'total_count' in mssql_df.columns else 0
    ms_done = mssql_df['done_count'].sum() if 'done_count' in mssql_df.columns else 0
    ms_doing = mssql_df['doing_count'].sum() if 'doing_count' in mssql_df.columns else 0
    ms_completion_rate = (ms_done / ms_total * 100) if ms_total > 0 else 0
    ms_progress_rate = ((ms_done + ms_doing) / ms_total * 100) if ms_total > 0 else 0
    
    completion_match = abs(ch_completion_rate - ms_completion_rate) < 0.1
    progress_match = abs(ch_progress_rate - ms_progress_rate) < 0.1
    
    print(f"{'✅' if completion_match else '❌'} 完成率        : ClickHouse={ch_completion_rate:5.1f}%, MSSQL={ms_completion_rate:5.1f}%")
    print(f"{'✅' if progress_match else '❌'} 執行率        : ClickHouse={ch_progress_rate:5.1f}%, MSSQL={ms_progress_rate:5.1f}%")
    
    if not completion_match:
        all_match = False
    if not progress_match:
        all_match = False
    
    print("\n" + "="*80)
    if all_match:
        print("🎉 對帳結果：完全一致！")
        print("✅ 所有指標都匹配，資料同步正確")
    else:
        print("⚠️ 對帳結果：發現差異！")
        print("❌ 部分指標不匹配，需要進一步調查")
        
        print("\n🔍 可能的差異原因:")
        print("1. V1/V3 歸屬邏輯差異（特別是 315% 工單號規則：使用 LIKE '315%' 涵蓋所有 315 開頭工單號）")
        print("2. NPE 判斷邏輯差異（BUSINESS_KEY vs varinst_name）")
        print("3. 日期篩選邏輯差異（START_TIME vs CLAIM_TIME vs END_TIME）")
        print("4. 排除條件差異（E/C 前綴、Q/R 工單）")
        print("5. 製造五階維度對應差異（WJ2/NBU/E5 識別邏輯）")
    
    print("="*80)
    return all_match

def main():
    """主執行函數"""
    print("🚀 開始 MSSQL vs ClickHouse 對帳驗證")
    print("📋 測試條件：V1 CNE WJ2 NBU E5 + 2025-12-30")
    print("="*80)
    
    # 建立連線
    print("\n🔗 建立資料庫連線...")
    ch_client = get_clickhouse_client()
    ms_conn = get_mssql_connection()
    
    if ch_client is None:
        print("❌ ClickHouse 連線失敗，無法繼續")
        return False
    
    if ms_conn is None:
        print("⚠️ MSSQL 連線失敗，僅顯示 ClickHouse 資料")
        
        # 僅查詢 ClickHouse 資料
        print("\n📊 查詢 ClickHouse 資料...")
        ch_df = query_clickhouse_data(ch_client)
        
        if ch_df is not None and len(ch_df) > 0:
            print("\n🔍 ClickHouse 查詢結果:")
            print(ch_df.to_string(index=False))
            
            # 計算指標
            total = ch_df['total_count'].sum()
            done = ch_df['done_count'].sum()
            doing = ch_df['doing_count'].sum()
            todo = ch_df['todo_count'].sum()
            
            completion_rate = (done / total * 100) if total > 0 else 0
            progress_rate = ((done + doing) / total * 100) if total > 0 else 0
            
            print(f"\n📈 ClickHouse 計算結果:")
            print(f"總任務數: {total}")
            print(f"TODO: {todo}, DOING: {doing}, DONE: {done}")
            print(f"完成率: {completion_rate:.1f}%")
            print(f"執行率: {progress_rate:.1f}%")
        else:
            print("❌ ClickHouse 沒有找到符合條件的資料")
        
        return False
    
    # 查詢兩個資料源
    print("\n📊 查詢 ClickHouse 資料...")
    ch_df = query_clickhouse_data(ch_client)
    
    print("\n📊 查詢 MSSQL 資料...")
    ms_df = query_mssql_data(ms_conn)
    
    # 比較結果
    result = compare_results(ch_df, ms_df)
    
    # 清理連線
    try:
        ch_client.close()
        ms_conn.close()
    except:
        pass
    
    return result

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)