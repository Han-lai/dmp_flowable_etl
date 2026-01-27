#!/usr/bin/env python3
"""
驗證 MSSQL 中 CNE WJ2 NBU E5 在 2025-12-25 的 V1/V2/V3 資料
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyodbc
from datetime import datetime

def get_mssql_connection():
    """建立 MSSQL 連線"""
    try:
        # 嘗試不同的 ODBC 驅動程式
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
                print(f"✓ 使用驅動程式: {driver}")
                return conn
            except Exception as e:
                print(f"✗ 驅動程式 {driver} 失敗: {e}")
                continue
        
        raise Exception("所有 ODBC 驅動程式都無法連線")
        
    except Exception as e:
        print(f"❌ MSSQL 連線失敗: {e}")
        return None

def query_mssql_data_by_vtype(conn, vtype, target_date='2025-12-25'):
    """查詢指定 Vtype 的 MSSQL 資料"""
    print(f"\n🔍 查詢 MSSQL {vtype} 資料 ({target_date})")
    
    # 根據 Vtype 調整查詢條件
    if vtype == 'V1':
        vtype_condition = """
        (var_moNumber.TEXT_ LIKE '315%' OR 
         var_moNumber.TEXT_ LIKE '196%' OR 
         var_moNumber.TEXT_ LIKE '199%' OR 
         var_moNumber.TEXT_ LIKE '200%' OR
         var_moNumber.TEXT_ LIKE '210%' OR 
         var_moNumber.TEXT_ LIKE '212%' OR 
         var_moNumber.TEXT_ LIKE '213%' OR
         pd.KEY_ LIKE 'V1%')
        """
    elif vtype == 'V2':
        vtype_condition = "pd.KEY_ LIKE 'V2%'"
    elif vtype == 'V3':
        vtype_condition = "pd.KEY_ LIKE 'V3%'"
    else:
        vtype_condition = "1=0"  # 無效條件
    
    mssql_query = f"""
    SELECT 
        '{vtype}' as vtype,
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
      AND ({vtype_condition})
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
        var_lineName.TEXT_
    
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
        print(f"❌ MSSQL {vtype} 查詢失敗: {e}")
        return []

def main():
    """主執行函數"""
    print("🚀 開始 MSSQL CNE WJ2 NBU E5 資料驗證")
    print("="*80)
    print("目標條件:")
    print("  REGION: CNE") 
    print("  FACTORY: WJ2")
    print("  PLANT: NBU")
    print("  LINE: E5")
    print("  日期: 2025-12-25")
    print("  VTYPE: V1, V2, V3")
    print("="*80)
    
    # 建立連線
    ms_conn = get_mssql_connection()
    
    if not ms_conn:
        print("❌ MSSQL 連線失敗，停止驗證")
        return False
    
    try:
        all_results = {}
        
        # 查詢各個 Vtype 的資料
        for vtype in ['V1', 'V2', 'V3']:
            results = query_mssql_data_by_vtype(ms_conn, vtype, '2025-12-25')
            all_results[vtype] = results
            
            if results:
                for row in results:
                    vtype, plant, factory, line, total, todo, doing, done, completion = row
                    print(f"  {vtype}: {plant}-{factory}-{line}")
                    print(f"    總任務: {total}, 待辦: {todo}, 進行中: {doing}, 已完成: {done}, 完成率: {completion}%")
            else:
                print(f"  {vtype}: 無資料")
        
        # 總結
        print("\n" + "="*80)
        print("🎯 MSSQL 資料驗證總結")
        print("="*80)
        
        total_vtypes_with_data = sum(1 for vtype, results in all_results.items() if results)
        
        if total_vtypes_with_data > 0:
            print(f"✅ 找到 {total_vtypes_with_data} 個 Vtype 有資料")
            for vtype, results in all_results.items():
                if results:
                    total_tasks = sum(row[4] for row in results)
                    print(f"📊 {vtype}: {total_tasks} 個任務")
        else:
            print("❌ 所有 Vtype 都無資料")
            print("🔍 可能原因：")
            print("  - 2025-12-25 日期無資料")
            print("  - CNE WJ2 NBU E5 條件無匹配資料")
            print("  - Vtype 判別邏輯需要調整")
        
        return total_vtypes_with_data > 0
        
    except Exception as e:
        print(f"❌ 驗證過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            ms_conn.close()
        except:
            pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)