#!/usr/bin/env python3
"""
MVIEW Pipeline 完成度驗證腳本
測試 MSSQL 原生資料與更新後的 MVIEW 內容比對

測試案例：CNE WJ2 NBU E5 2025-12-31 分別 V1/V2/V3 的任務數
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
            password='default'
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

def check_mview_tables(client):
    """檢查 MVIEW 表是否存在並獲取基本資訊"""
    print("\n🔍 檢查 MVIEW 表狀態...")
    print("="*60)
    
    tables_to_check = [
        'silver.mv_fact_task_vx_attribution',
        'silver.mv_fact_task_vx_attribution_native',
        'silver.mv_fact_task_vx_attribution_native_simple',
        'silver.mv_l5_metrics_realtime',
        'silver.mv_l5_metrics_realtime_native',
        'silver.mv_varinst_pivoted'
    ]
    
    table_status = {}
    
    for table in tables_to_check:
        try:
            # 檢查表是否存在
            result = client.query(f"SELECT COUNT(*) as count FROM {table} LIMIT 1")
            count_result = client.query(f"SELECT COUNT(*) as total_count FROM {table}")
            total_count = count_result.result_rows[0][0]
            
            table_status[table] = {
                'exists': True,
                'count': total_count
            }
            print(f"✅ {table}: {total_count:,} 筆記錄")
            
        except Exception as e:
            table_status[table] = {
                'exists': False,
                'error': str(e)
            }
            print(f"❌ {table}: 不存在或查詢失敗 - {e}")
    
    return table_status

def query_clickhouse_mview_data(client, test_date='2025-12-31'):
    """查詢 ClickHouse MVIEW 資料 - 分別查詢 V1/V2/V3"""
    
    # 先檢查哪個表可用
    available_table = None
    for table in ['silver.mv_fact_task_vx_attribution', 'silver.mv_fact_task_vx_attribution_native_simple']:
        try:
            client.query(f"SELECT 1 FROM {table} LIMIT 1")
            available_table = table
            print(f"✅ 使用表: {available_table}")
            break
        except:
            continue
    
    if not available_table:
        print("❌ 沒有可用的 MVIEW 表")
        return None
    
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
    FROM {available_table}
    WHERE (
        toDate(task_create_time) = '{test_date}'
        OR toDate(task_claim_time) = '{test_date}'
        OR toDate(task_end_time) = '{test_date}'
    )
      AND vx_type IN ('V1', 'V2', 'V3')
      AND plant = 'WJ2'
      AND factory = 'NBU' 
      AND line = 'E5'
    GROUP BY vx_type, plant, factory, line
    ORDER BY vx_type
    """
    
    try:
        result = client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        print(f"✅ ClickHouse MVIEW 查詢成功，返回 {len(df)} 筆資料")
        return df, available_table
    except Exception as e:
        print(f"❌ ClickHouse MVIEW 查詢失敗: {e}")
        return None, None

def query_mssql_native_data(conn, test_date='2025-12-31'):
    """查詢 MSSQL 原生資料 - 分別查詢 V1/V2/V3"""
    
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
            
            -- V1/V2/V3 歸屬邏輯（修正後：工單號規則優先）
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
    WHERE vx_type IN ('V1', 'V2', 'V3')
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
    GROUP BY vx_type, plant, factory, line
    ORDER BY vx_type
    """
    
    try:
        df = pd.read_sql(query, conn)
        print(f"✅ MSSQL 原生資料查詢成功，返回 {len(df)} 筆資料")
        return df
    except Exception as e:
        print(f"❌ MSSQL 原生資料查詢失敗: {e}")
        return None

def compare_vx_results(clickhouse_df, mssql_df, table_name):
    """比較 V1/V2/V3 的結果"""
    print("\n" + "="*80)
    print(f"📊 MSSQL 原生資料 vs ClickHouse MVIEW ({table_name}) 比對結果")
    print("📋 測試條件：CNE WJ2 NBU E5 + 2025-12-31")
    print("="*80)
    
    if clickhouse_df is None or mssql_df is None:
        print("❌ 無法進行比較，其中一個資料源查詢失敗")
        return False
    
    # 顯示原始資料
    print("\n🔍 ClickHouse MVIEW 查詢結果:")
    if len(clickhouse_df) > 0:
        print(clickhouse_df.to_string(index=False))
    else:
        print("  (無資料)")
    
    print("\n🔍 MSSQL 原生資料查詢結果:")
    if len(mssql_df) > 0:
        print(mssql_df.to_string(index=False))
    else:
        print("  (無資料)")
    
    # 建立 V1/V2/V3 的完整比較表
    vx_types = ['V1', 'V2', 'V3']
    metrics = ['todo_count', 'doing_count', 'done_count', 'total_count', 'excluded_count']
    
    print("\n📈 V1/V2/V3 任務數比較:")
    print("-" * 100)
    print(f"{'Vx類型':<6} {'指標':<15} {'ClickHouse':<12} {'MSSQL':<12} {'差異':<8} {'狀態':<6}")
    print("-" * 100)
    
    all_match = True
    summary_data = {}
    
    for vx_type in vx_types:
        # 取得該 Vx 類型的資料
        ch_row = clickhouse_df[clickhouse_df['vx_type'] == vx_type] if len(clickhouse_df) > 0 else pd.DataFrame()
        ms_row = mssql_df[mssql_df['vx_type'] == vx_type] if len(mssql_df) > 0 else pd.DataFrame()
        
        summary_data[vx_type] = {}
        
        for metric in metrics:
            ch_value = ch_row[metric].iloc[0] if len(ch_row) > 0 and metric in ch_row.columns else 0
            ms_value = ms_row[metric].iloc[0] if len(ms_row) > 0 and metric in ms_row.columns else 0
            
            summary_data[vx_type][metric] = {
                'clickhouse': ch_value,
                'mssql': ms_value,
                'diff': ch_value - ms_value,
                'match': ch_value == ms_value
            }
            
            status = "✅" if ch_value == ms_value else "❌"
            if ch_value != ms_value:
                all_match = False
            
            print(f"{vx_type:<6} {metric:<15} {ch_value:<12} {ms_value:<12} {ch_value-ms_value:+8} {status:<6}")
    
    # 計算總計
    print("-" * 100)
    for metric in metrics:
        ch_total = sum([summary_data[vx][metric]['clickhouse'] for vx in vx_types])
        ms_total = sum([summary_data[vx][metric]['mssql'] for vx in vx_types])
        diff = ch_total - ms_total
        status = "✅" if diff == 0 else "❌"
        
        print(f"{'總計':<6} {metric:<15} {ch_total:<12} {ms_total:<12} {diff:+8} {status:<6}")
    
    # 計算完成率和執行率
    print("\n📊 V1/V2/V3 完成率和執行率比較:")
    print("-" * 80)
    print(f"{'Vx類型':<6} {'資料源':<12} {'總數':<8} {'完成率':<10} {'執行率':<10}")
    print("-" * 80)
    
    for vx_type in vx_types:
        data = summary_data[vx_type]
        
        # ClickHouse 計算
        ch_total = data['total_count']['clickhouse']
        ch_done = data['done_count']['clickhouse']
        ch_doing = data['doing_count']['clickhouse']
        ch_completion_rate = (ch_done / ch_total * 100) if ch_total > 0 else 0
        ch_progress_rate = ((ch_done + ch_doing) / ch_total * 100) if ch_total > 0 else 0
        
        # MSSQL 計算
        ms_total = data['total_count']['mssql']
        ms_done = data['done_count']['mssql']
        ms_doing = data['doing_count']['mssql']
        ms_completion_rate = (ms_done / ms_total * 100) if ms_total > 0 else 0
        ms_progress_rate = ((ms_done + ms_doing) / ms_total * 100) if ms_total > 0 else 0
        
        print(f"{vx_type:<6} {'ClickHouse':<12} {ch_total:<8} {ch_completion_rate:>8.1f}% {ch_progress_rate:>8.1f}%")
        print(f"{'':<6} {'MSSQL':<12} {ms_total:<8} {ms_completion_rate:>8.1f}% {ms_progress_rate:>8.1f}%")
        print()
    
    print("="*80)
    if all_match:
        print("🎉 MVIEW Pipeline 驗證結果：完全一致！")
        print("✅ 所有 V1/V2/V3 任務數都匹配，MVIEW 更新成功")
        print("✅ 原生表替換邏輯正確，資料同步完整")
    else:
        print("⚠️ MVIEW Pipeline 驗證結果：發現差異！")
        print("❌ 部分 V1/V2/V3 任務數不匹配，需要進一步調查")
        
        print("\n🔍 可能的差異原因:")
        print("1. MVIEW 表尚未更新或重建")
        print("2. V1/V3 歸屬邏輯差異（315% 工單號規則）")
        print("3. 原生表欄位映射問題")
        print("4. 時間篩選邏輯差異")
        print("5. 排除條件邏輯差異")
        
        print("\n🛠️ 建議修正步驟:")
        print("1. 重建 MVIEW 表：執行 sql/12_create_silver_mviews_layer2.sql")
        print("2. 檢查 silver.mv_varinst_pivoted 是否正確")
        print("3. 驗證原生表 JOIN 邏輯")
        print("4. 確認 315% 工單號規則實施")
    
    print("="*80)
    return all_match

def main():
    """主執行函數"""
    try:
        print("🚀 開始 MVIEW Pipeline 完成度驗證")
        print("📋 測試條件：CNE WJ2 NBU E5 + 2025-12-31 分別 V1/V2/V3 任務數")
        print("="*80)
        
        # 建立連線
        print("\n🔗 建立資料庫連線...")
        ch_client = get_clickhouse_client()
        ms_conn = get_mssql_connection()
        
        if ch_client is None:
            print("❌ ClickHouse 連線失敗，無法繼續")
            return False
        
        # 檢查 MVIEW 表狀態
        table_status = check_mview_tables(ch_client)
        
        if ms_conn is None:
            print("⚠️ MSSQL 連線失敗，僅顯示 ClickHouse MVIEW 資料")
            
            # 僅查詢 ClickHouse 資料
            print("\n📊 查詢 ClickHouse MVIEW 資料...")
            ch_result = query_clickhouse_mview_data(ch_client)
            
            if ch_result and ch_result[0] is not None:
                ch_df, table_name = ch_result
                print(f"\n🔍 ClickHouse MVIEW ({table_name}) 查詢結果:")
                print(ch_df.to_string(index=False))
            else:
                print("❌ ClickHouse MVIEW 沒有找到符合條件的資料")
            
            return False
        
        # 查詢兩個資料源
        print("\n📊 查詢 ClickHouse MVIEW 資料...")
        ch_result = query_clickhouse_mview_data(ch_client)
        
        print("\n📊 查詢 MSSQL 原生資料...")
        ms_df = query_mssql_native_data(ms_conn)
        
        # 比較結果
        if ch_result:
            ch_df, table_name = ch_result
            result = compare_vx_results(ch_df, ms_df, table_name)
        else:
            result = False
        
        # 清理連線
        try:
            ch_client.close()
            ms_conn.close()
        except:
            pass
        
        return result
        
    except Exception as e:
        print(f"❌ 執行過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)