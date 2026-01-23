#!/usr/bin/env python3
"""
比較 MSSQL 與 ClickHouse 中 CNE WJ2 NBU E5 在 2025-11-24 的資料
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect
import pyodbc
from datetime import datetime

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
        drivers = [
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server", 
            "SQL Server Native Client 11.0",
            "SQL Server"
        ]
        
        for driver in drivers:
            try:
                conn_str = (
                    f"DRIVER={{{driver}}};"
                    "SERVER=twtpesqldv2.delta.corp,1433;"
                    "DATABASE=APP_SRV_BPM;"
                    "UID=DMP_APP_SRV;"
                    "PWD=APP@DB#01;"
                )
                conn = pyodbc.connect(conn_str)
                print(f"✓ MSSQL 使用驅動程式: {driver}")
                return conn
            except Exception as e:
                continue
        
        raise Exception("所有 ODBC 驅動程式都無法連線")
        
    except Exception as e:
        print(f"❌ MSSQL 連線失敗: {e}")
        return None

def query_clickhouse_data(client, target_date='2025-11-24'):
    """查詢 ClickHouse 資料"""
    print(f"\n🔵 查詢 ClickHouse 資料 ({target_date})")
    
    # 先檢查表結構
    try:
        columns_result = client.query("DESCRIBE silver.mv_fact_task_vx_attribution_mdm")
        available_columns = [row[0] for row in columns_result.result_rows]
        print(f"  可用欄位: {', '.join(available_columns[:10])}...")  # 顯示前10個欄位
    except Exception as e:
        print(f"  ⚠️ 無法檢查表結構: {e}")
    
    # 查詢修正後的 MVIEW
    query = f"""
    SELECT 
        'ClickHouse' as source,
        vx_type,
        plant_code,
        factory_code,
        COUNT(*) as total_tasks,
        SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_tasks,
        SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_tasks,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_tasks,
        ROUND(SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as completion_rate
    FROM silver.mv_fact_task_vx_attribution_mdm FINAL
    WHERE task_create_date = '{target_date}'
      AND plant_code = 'NBU'
      AND factory_code = 'WJ2'
    GROUP BY vx_type, plant_code, factory_code
    ORDER BY vx_type
    """
    
    try:
        result = client.query(query)
        return result.result_rows
    except Exception as e:
        print(f"❌ ClickHouse 查詢失敗: {e}")
        
        # 嘗試簡化查詢
        simple_query = f"""
        SELECT 
            vx_type,
            plant_code,
            factory_code,
            COUNT(*) as total_tasks
        FROM silver.mv_fact_task_vx_attribution_mdm FINAL
        WHERE task_create_date = '{target_date}'
          AND plant_code = 'NBU'
          AND factory_code = 'WJ2'
        GROUP BY vx_type, plant_code, factory_code
        ORDER BY vx_type
        """
        
        try:
            print("  🔄 嘗試簡化查詢...")
            result = client.query(simple_query)
            return [(row[0], row[1], row[2], row[3], 0, 0, 0, 0.0) for row in result.result_rows]
        except Exception as e2:
            print(f"❌ 簡化查詢也失敗: {e2}")
            return []

def query_mssql_data(conn, target_date='2025-11-24'):
    """查詢 MSSQL 資料"""
    print(f"\n🟡 查詢 MSSQL 資料 ({target_date})")
    
    # 查詢所有 Vtype 的資料
    mssql_query = f"""
    SELECT 
        'MSSQL' as source,
        CASE 
            WHEN (var_moNumber.TEXT_ LIKE '315%' OR 
                  var_moNumber.TEXT_ LIKE '196%' OR 
                  var_moNumber.TEXT_ LIKE '199%' OR 
                  var_moNumber.TEXT_ LIKE '200%' OR
                  var_moNumber.TEXT_ LIKE '210%' OR 
                  var_moNumber.TEXT_ LIKE '212%' OR 
                  var_moNumber.TEXT_ LIKE '213%' OR
                  pd.KEY_ LIKE 'V1%') THEN 'V1'
            WHEN pd.KEY_ LIKE 'V2%' THEN 'V2'
            WHEN pd.KEY_ LIKE 'V3%' THEN 'V3'
            ELSE 'Unknown'
        END as vx_type,
        var_plant.TEXT_ as plant,
        var_factory.TEXT_ as factory,
        var_lineName.TEXT_ as line,
        
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
      AND ( 
          hti.START_TIME_ BETWEEN '{target_date} 00:00:00' AND '{target_date} 23:59:59'
          OR hti.CLAIM_TIME_ BETWEEN '{target_date} 00:00:00' AND '{target_date} 23:59:59'
          OR hti.END_TIME_ BETWEEN '{target_date} 00:00:00' AND '{target_date} 23:59:59'
      )
      AND (
          (var_plant.TEXT_ = 'WJ2' AND var_factory.TEXT_ = 'NBU' AND var_lineName.TEXT_ = 'E5') OR
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
        CASE 
            WHEN (var_moNumber.TEXT_ LIKE '315%' OR 
                  var_moNumber.TEXT_ LIKE '196%' OR 
                  var_moNumber.TEXT_ LIKE '199%' OR 
                  var_moNumber.TEXT_ LIKE '200%' OR
                  var_moNumber.TEXT_ LIKE '210%' OR 
                  var_moNumber.TEXT_ LIKE '212%' OR 
                  var_moNumber.TEXT_ LIKE '213%' OR
                  pd.KEY_ LIKE 'V1%') THEN 'V1'
            WHEN pd.KEY_ LIKE 'V2%' THEN 'V2'
            WHEN pd.KEY_ LIKE 'V3%' THEN 'V3'
            ELSE 'Unknown'
        END,
        var_plant.TEXT_,
        var_factory.TEXT_,
        var_lineName.TEXT_
    
    ORDER BY 
        CASE 
            WHEN (var_moNumber.TEXT_ LIKE '315%' OR 
                  var_moNumber.TEXT_ LIKE '196%' OR 
                  var_moNumber.TEXT_ LIKE '199%' OR 
                  var_moNumber.TEXT_ LIKE '200%' OR
                  var_moNumber.TEXT_ LIKE '210%' OR 
                  var_moNumber.TEXT_ LIKE '212%' OR 
                  var_moNumber.TEXT_ LIKE '213%' OR
                  pd.KEY_ LIKE 'V1%') THEN 'V1'
            WHEN pd.KEY_ LIKE 'V2%' THEN 'V2'
            WHEN pd.KEY_ LIKE 'V3%' THEN 'V3'
            ELSE 'Unknown'
        END
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
    print("📊 MSSQL vs ClickHouse 數值比較 (2025-11-24)")
    print("="*80)
    
    print("\n🔵 ClickHouse 結果:")
    ch_summary = {}
    if clickhouse_results:
        for row in clickhouse_results:
            source, vx_type, plant, factory, total, todo, doing, done, completion = row
            print(f"  {vx_type}: Plant={plant}, Factory={factory}")
            print(f"    總任務: {total}, 待辦: {todo}, 進行中: {doing}, 已完成: {done}, 完成率: {completion}%")
            ch_summary[vx_type] = {
                'total': total,
                'done': done,
                'completion': completion
            }
    else:
        print("  ❌ 無資料")
    
    print("\n🟡 MSSQL 結果:")
    ms_summary = {}
    if mssql_results:
        for row in mssql_results:
            source, vx_type, plant, factory, line, total, todo, doing, done, completion = row
            print(f"  {vx_type}: Plant={plant}, Factory={factory}, Line={line}")
            print(f"    總任務: {total}, 待辦: {todo}, 進行中: {doing}, 已完成: {done}, 完成率: {completion}%")
            ms_summary[vx_type] = {
                'total': total,
                'done': done,
                'completion': completion
            }
    else:
        print("  ❌ 無資料")
    
    # 數值比較分析
    print("\n📈 數值一致性分析:")
    
    all_vtypes = set(ch_summary.keys()) | set(ms_summary.keys())
    
    if not all_vtypes:
        print("  ⚠️ 兩邊都無資料")
        return False
    
    consistent_count = 0
    total_comparisons = 0
    
    for vtype in sorted(all_vtypes):
        print(f"\n  📋 {vtype} 比較:")
        
        if vtype in ch_summary and vtype in ms_summary:
            ch_data = ch_summary[vtype]
            ms_data = ms_summary[vtype]
            
            total_diff = abs(ch_data['total'] - ms_data['total'])
            completion_diff = abs(ch_data['completion'] - ms_data['completion'])
            
            print(f"    總任務數: ClickHouse={ch_data['total']}, MSSQL={ms_data['total']}")
            print(f"    完成率: ClickHouse={ch_data['completion']}%, MSSQL={ms_data['completion']}%")
            
            if total_diff == 0:
                print(f"    ✅ 總任務數一致")
                consistent_count += 1
            else:
                print(f"    ❌ 總任務數不一致 (差異: {total_diff})")
            
            if completion_diff < 0.1:
                print(f"    ✅ 完成率一致")
                consistent_count += 1
            else:
                print(f"    ❌ 完成率不一致 (差異: {completion_diff}%)")
            
            total_comparisons += 2
            
        elif vtype in ch_summary:
            print(f"    ❌ 只有 ClickHouse 有資料: {ch_summary[vtype]['total']} 個任務")
        else:
            print(f"    ❌ 只有 MSSQL 有資料: {ms_summary[vtype]['total']} 個任務")
    
    consistency_rate = (consistent_count / total_comparisons * 100) if total_comparisons > 0 else 0
    print(f"\n  📊 整體一致性: {consistent_count}/{total_comparisons} ({consistency_rate:.1f}%)")
    
    return consistency_rate >= 80

def main():
    """主執行函數"""
    print("🚀 開始 MSSQL vs ClickHouse 資料比較")
    print("="*80)
    print("目標條件:")
    print("  REGION: CNE") 
    print("  FACTORY: WJ2")
    print("  PLANT: NBU")
    print("  LINE: E5")
    print("  日期: 2025-12-25 (12月份資料)")
    print("="*80)
    
    # 建立連線
    ch_client = get_clickhouse_client()
    ms_conn = get_mssql_connection()
    
    if not ch_client:
        print("❌ ClickHouse 連線失敗，停止比較")
        return False
    
    if not ms_conn:
        print("❌ MSSQL 連線失敗，停止比較")
        return False
    
    try:
        # 查詢資料 - 使用12月份的日期
        ch_results = query_clickhouse_data(ch_client, '2025-12-25')
        ms_results = query_mssql_data(ms_conn, '2025-12-25')
        
        # 比較結果
        is_consistent = compare_results(ch_results, ms_results)
        
        # 總結
        print("\n" + "="*80)
        print("🎯 比較總結")
        print("="*80)
        
        if is_consistent:
            print("✅ 資料一致性驗證通過")
            print("📊 MSSQL 與 ClickHouse 資料基本一致")
        else:
            print("❌ 資料一致性驗證失敗")
            print("🔍 發現數值差異，需要進一步檢查")
        
        return is_consistent
        
    except Exception as e:
        print(f"❌ 比較過程發生錯誤: {e}")
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