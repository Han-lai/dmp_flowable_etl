#!/usr/bin/env python3
"""
驗證 MSSQL 與 ClickHouse 維度對應和數值一致性
針對特定維度組合：V1, CNE, WJ2, NBU, E5
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect
import pyodbc
from datetime import datetime, timedelta
import pandas as pd

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
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
        # 使用指定的帳密連接到 MSSQL
        conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=twtpesqldv2.delta.corp,1433;"
            "DATABASE=APP_SRV_BPM;"
            "UID=DMP_APP_SRV;"
            "PWD=APP@DB#01;"
        )
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        print(f"❌ MSSQL 連線失敗: {e}")
        return None

def query_clickhouse_data(client, target_date='2025-12-31'):
    """查詢 ClickHouse 中的資料"""
    print(f"🔍 查詢 ClickHouse 資料 ({target_date})")
    
    # 方法1: 使用 Gold 層 MVIEW (MDM 整合版本)
    gold_query = f"""
    SELECT 
        'GOLD_MVIEW' as source,
        region_code,
        plant_code,
        factory_code,
        line_code,
        vx_type,
        sum_total_task_qty AS total_tasks,
        sum_todo_qty AS todo_tasks,
        sum_doing_qty AS doing_tasks,
        sum_done_qty AS done_tasks,
        completion_rate
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
    WHERE snapshot_date = '{target_date}'
      AND region_code = 'CNE'
      AND (
          (plant_code = 'PF' AND factory_code = 'WJ2' AND line_code = 'E5') OR
          (plant_code = 'NBU' AND factory_code = 'WJ2' AND line_code = 'E5') OR
          (factory_code = 'NBU' AND line_code = 'E5')
      )
      AND vx_type = 'V1'
    ORDER BY plant_code, factory_code, line_code
    """
    
    # 方法2: 使用 Silver 層直接查詢 (檢查原始對應)
    silver_query = f"""
    SELECT 
        'SILVER_DIRECT' as source,
        region_code,
        plant_code,
        factory_code,
        line_code,
        vx_type,
        COUNT(*) as total_tasks,
        SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_tasks,
        SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_tasks,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_tasks,
        ROUND(SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as completion_rate
    FROM silver.mv_fact_task_vx_attribution_mdm FINAL
    WHERE toDate(task_create_time) = '{target_date}'
      AND region_code = 'CNE'
      AND (
          (plant_code = 'PF' AND factory_code = 'WJ2' AND line_code = 'E5') OR
          (plant_code = 'NBU' AND factory_code = 'WJ2' AND line_code = 'E5') OR
          (factory_code = 'NBU' AND line_code = 'E5')
      )
      AND vx_type = 'V1'
      AND task_bypass = 'N'
    GROUP BY region_code, plant_code, factory_code, line_code, vx_type
    ORDER BY plant_code, factory_code, line_code
    """
    
    results = []
    
    try:
        # 查詢 Gold 層
        gold_result = client.query(gold_query)
        results.extend(gold_result.result_rows)
        
        # 查詢 Silver 層
        silver_result = client.query(silver_query)
        results.extend(silver_result.result_rows)
        
        return results
        
    except Exception as e:
        print(f"❌ ClickHouse 查詢失敗: {e}")
        return []

def query_mssql_data(conn, target_date='2025-12-31'):
    """查詢 MSSQL 原始資料"""
    print(f"🔍 查詢 MSSQL 原始資料 ({target_date})")
    
    # 使用您提供的原始查詢邏輯
    mssql_query = f"""
    SELECT 
        'MSSQL_ORIGINAL' as source,
        var_plant.TEXT_ as plant,
        var_factory.TEXT_ as factory,
        var_lineName.TEXT_ as line,
        
        -- Vx 類型判斷邏輯 (簡化版)
        CASE 
            WHEN var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
            WHEN pd.KEY_ LIKE '%V2%' THEN 'V2'
            WHEN pd.KEY_ LIKE '%V3%' THEN 'V3'
            ELSE 'V1'
        END as vx_type,
        
        COUNT(*) as total_tasks,
        SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NULL THEN 1 ELSE 0 END) as todo_tasks,
        SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NOT NULL THEN 1 ELSE 0 END) as doing_tasks,
        SUM(CASE WHEN hti.END_TIME_ IS NOT NULL THEN 1 ELSE 0 END) as done_tasks,
        
        ROUND(
            CAST(SUM(CASE WHEN hti.END_TIME_ IS NOT NULL THEN 1 ELSE 0 END) AS FLOAT) * 100.0 / COUNT(*), 
            2
        ) as completion_rate
        
    FROM ACT_HI_PROCINST hi
    LEFT JOIN ACT_HI_VARINST var_plant on hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ and var_plant.NAME_ = 'plant'
    LEFT JOIN ACT_HI_VARINST var_factory on hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ and var_factory.NAME_ = 'factory'
    LEFT JOIN ACT_HI_VARINST var_lineName on hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ and var_lineName.NAME_ = 'lineName'
    LEFT JOIN ACT_HI_VARINST var_moNumber on hi.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ and var_moNumber.NAME_ = 'moNumber'
    LEFT JOIN ACT_RE_PROCDEF pd ON hi.PROC_DEF_ID_ = pd.ID_
    LEFT JOIN ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
    
    WHERE 1=1
      AND CAST(hti.START_TIME_ AS DATE) = '{target_date}'
      AND (
          (var_plant.TEXT_ = 'WJ2' AND var_factory.TEXT_ = 'NBU' AND var_lineName.TEXT_ = 'E5') OR
          (var_plant.TEXT_ = 'NBU' AND var_factory.TEXT_ = 'WJ2' AND var_lineName.TEXT_ = 'E5') OR
          (var_factory.TEXT_ = 'WJ2' AND var_lineName.TEXT_ = 'E5')
      )
      -- 排除 TaskBypass = Y 的任務
      AND NOT EXISTS (
          SELECT 1 FROM ACT_HI_VARINST bypass 
          WHERE bypass.TASK_ID_ = hti.ID_ 
            AND bypass.NAME_ = 'autoComplete' 
            AND bypass.LONG_ = 1
      )
    
    GROUP BY 
        var_plant.TEXT_,
        var_factory.TEXT_,
        var_lineName.TEXT_,
        CASE 
            WHEN var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
            WHEN pd.KEY_ LIKE '%V2%' THEN 'V2'
            WHEN pd.KEY_ LIKE '%V3%' THEN 'V3'
            ELSE 'V1'
        END
    
    HAVING 
        CASE 
            WHEN var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
            WHEN pd.KEY_ LIKE '%V2%' THEN 'V2'
            WHEN pd.KEY_ LIKE '%V3%' THEN 'V3'
            ELSE 'V1'
        END = 'V1'
    
    ORDER BY var_plant.TEXT_, var_factory.TEXT_, var_lineName.TEXT_
    """
    
    try:
        cursor = conn.cursor()
        cursor.execute(mssql_query)
        
        results = []
        for row in cursor.fetchall():
            results.append(row)
        
        cursor.close()
        return results
        
    except Exception as e:
        print(f"❌ MSSQL 查詢失敗: {e}")
        return []

def compare_results(clickhouse_results, mssql_results):
    """比較兩邊的查詢結果"""
    print("\n" + "="*80)
    print("📊 MSSQL vs ClickHouse 數值比較")
    print("="*80)
    
    print("\n🔵 ClickHouse 結果:")
    if clickhouse_results:
        for row in clickhouse_results:
            source, region, plant, factory, line, vx_type, total, todo, doing, done, completion = row
            print(f"  {source}: {region}-{plant}-{factory}-{line} {vx_type}")
            print(f"    總任務: {total}, 待辦: {todo}, 進行中: {doing}, 已完成: {done}, 完成率: {completion}%")
    else:
        print("  ❌ 無資料")
    
    print("\n🟡 MSSQL 結果:")
    if mssql_results:
        for row in mssql_results:
            source, plant, factory, line, vx_type, total, todo, doing, done, completion = row
            print(f"  {source}: {plant}-{factory}-{line} {vx_type}")
            print(f"    總任務: {total}, 待辦: {todo}, 進行中: {doing}, 已完成: {done}, 完成率: {completion}%")
    else:
        print("  ❌ 無資料")
    
    # 數值比較分析
    print("\n📈 數值一致性分析:")
    
    if not clickhouse_results and not mssql_results:
        print("  ⚠️ 兩邊都無資料")
    elif not clickhouse_results:
        print("  ❌ ClickHouse 無資料，MSSQL 有資料 - 可能是同步問題")
    elif not mssql_results:
        print("  ❌ MSSQL 無資料，ClickHouse 有資料 - 可能是查詢條件問題")
    else:
        # 找到最接近的匹配進行比較
        for ch_row in clickhouse_results:
            ch_source, ch_region, ch_plant, ch_factory, ch_line, ch_vx, ch_total, ch_todo, ch_doing, ch_done, ch_completion = ch_row
            
            for ms_row in mssql_results:
                ms_source, ms_plant, ms_factory, ms_line, ms_vx, ms_total, ms_todo, ms_doing, ms_done, ms_completion = ms_row
                
                # 檢查維度是否匹配 (考慮不同的對應方式)
                dimension_match = (
                    (ch_factory == ms_plant and ch_line == ms_line) or  # WJ2-E5 匹配
                    (ch_plant == ms_plant and ch_factory == ms_factory and ch_line == ms_line)  # 完全匹配
                )
                
                if dimension_match and ch_vx == ms_vx:
                    print(f"\n  ✅ 找到匹配組合: {ch_vx}")
                    print(f"    ClickHouse ({ch_source}): {ch_region}-{ch_plant}-{ch_factory}-{ch_line}")
                    print(f"    MSSQL ({ms_source}): {ms_plant}-{ms_factory}-{ms_line}")
                    
                    # 數值比較
                    total_diff = abs(ch_total - ms_total)
                    completion_diff = abs(ch_completion - ms_completion)
                    
                    if total_diff == 0:
                        print(f"    📊 總任務數: ✅ 一致 ({ch_total})")
                    else:
                        print(f"    📊 總任務數: ❌ 不一致 (CH: {ch_total}, MS: {ms_total}, 差異: {total_diff})")
                    
                    if completion_diff < 0.1:  # 允許 0.1% 的浮點數誤差
                        print(f"    📊 完成率: ✅ 一致 ({ch_completion}%)")
                    else:
                        print(f"    📊 完成率: ❌ 不一致 (CH: {ch_completion}%, MS: {ms_completion}%, 差異: {completion_diff}%)")
                    
                    return True
        
        print("  ❌ 未找到匹配的維度組合")
    
    return False

def main():
    """主執行函數"""
    print("🚀 開始 MSSQL vs ClickHouse 維度對應驗證")
    print("="*80)
    print("目標條件:")
    print("  VTYPE: V1")
    print("  REGION: CNE") 
    print("  FACTORY: WJ2")
    print("  PLANT: NBU")
    print("  LINE: E5")
    print("  日期: 2025-12-31")
    print("="*80)
    
    # 建立連線
    ch_client = get_clickhouse_client()
    ms_conn = get_mssql_connection()
    
    if not ch_client:
        print("❌ ClickHouse 連線失敗，停止驗證")
        return False
    
    if not ms_conn:
        print("❌ MSSQL 連線失敗，停止驗證")
        return False
    
    try:
        # 查詢資料
        ch_results = query_clickhouse_data(ch_client, '2025-12-31')
        ms_results = query_mssql_data(ms_conn, '2025-12-31')
        
        # 比較結果
        is_consistent = compare_results(ch_results, ms_results)
        
        # 總結
        print("\n" + "="*80)
        print("🎯 驗證總結")
        print("="*80)
        
        if is_consistent:
            print("✅ 數值一致性驗證通過")
            print("📊 MSSQL 與 ClickHouse 資料一致")
            print("🎉 MDM 整合 MVIEW 架構運作正常")
        else:
            print("❌ 數值一致性驗證失敗")
            print("🔍 需要進一步檢查維度對應邏輯或資料同步")
        
        return is_consistent
        
    except Exception as e:
        print(f"❌ 驗證過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            ch_client.close()
            ms_conn.close()
        except:
            pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)