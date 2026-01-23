#!/usr/bin/env python3
"""
測試 MSSQL Vx 歸屬邏輯
驗證工單號規則和 TaskDefinitionKey 規則的正確性
"""

import pyodbc
from datetime import datetime

def connect_mssql():
    """連接 MSSQL"""
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

def test_vx_logic():
    """測試 Vx 歸屬邏輯"""
    print("=== 測試 MSSQL Vx 歸屬邏輯 ===")
    
    conn = connect_mssql()
    if not conn:
        print("❌ MSSQL 連線失敗")
        return
    
    # 您提供的 SQL 查詢（移除維度條件，專注測試 Vx 邏輯）
    sql = """
    SELECT 
        -- Vx 歸屬（工單號規則優先）
        CASE 
            WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%'
                 OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%'
                 OR var_moNumber.TEXT_ LIKE '315%'
            THEN 'V1'
            WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
            WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
            WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
            ELSE SUBSTRING(hti.TASK_DEF_KEY_, 1, 2)
        END as vxType,
        
        var_plant.TEXT_ as plant,
        var_factory.TEXT_ as factory,
        var_lineName.TEXT_ as line,
        var_moNumber.TEXT_ as moNumber,
        hti.TASK_DEF_KEY_ as taskDefKey,
        
        COUNT(*) as totalTasks,
        SUM(CASE WHEN (CASE WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE' WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING' ELSE 'TODO' END) = 'TODO' THEN 1 ELSE 0 END) as todoTasks,
        SUM(CASE WHEN (CASE WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE' WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING' ELSE 'TODO' END) = 'DOING' THEN 1 ELSE 0 END) as doingTasks,
        SUM(CASE WHEN (CASE WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE' WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING' ELSE 'TODO' END) = 'DONE' THEN 1 ELSE 0 END) as doneTasks,
        CASE 
            WHEN COUNT(*) > 0 
            THEN ROUND(SUM(CASE WHEN (CASE WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE' WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING' ELSE 'TODO' END) = 'DONE' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2)
            ELSE 0.0
        END as completionRate
        
    FROM ACT_HI_PROCINST hi 
    LEFT JOIN ACT_HI_VARINST var_plant on hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ and var_plant.NAME_ = 'plant' 
    LEFT JOIN ACT_HI_VARINST var_factory on hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ and var_factory.NAME_ = 'factory' 
    LEFT JOIN ACT_HI_VARINST var_lineName on hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ and var_lineName.NAME_ = 'lineName' 
    LEFT JOIN ACT_HI_VARINST var_moNumber on hi.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ and var_moNumber.NAME_ = 'moNumber' 
    LEFT JOIN ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_ 
    WHERE 1=1 
      AND ( hti.START_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
            OR hti.CLAIM_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
            OR hti.END_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59' )
      -- 移除維度條件，專注測試 Vx 邏輯
      -- AND var_plant.TEXT_ = 'NBU'
      -- AND var_factory.TEXT_ = 'WJ2'
      -- AND var_lineName.TEXT_ = 'E5'
      AND (
          CASE 
              WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%'
                   OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%'
                   OR var_moNumber.TEXT_ LIKE '315%'
              THEN 'V1'
              WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
              WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
              WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
              ELSE SUBSTRING(hti.TASK_DEF_KEY_, 1, 2)
          END
      ) = 'V3'
    GROUP BY 
        CASE 
            WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%'
                 OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%'
                 OR var_moNumber.TEXT_ LIKE '315%'
            THEN 'V1'
            WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
            WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
            WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
            ELSE SUBSTRING(hti.TASK_DEF_KEY_, 1, 2)
        END,
        var_plant.TEXT_,
        var_factory.TEXT_,
        var_lineName.TEXT_,
        var_moNumber.TEXT_,
        hti.TASK_DEF_KEY_
    ORDER BY var_plant.TEXT_, var_factory.TEXT_, var_lineName.TEXT_
    """
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        
        print("MSSQL Vx 邏輯測試結果:")
        if results:
            print(f"找到 {len(results)} 筆 V3 資料:")
            for row in results:
                vxType, plant, factory, line, moNumber, taskDefKey, total, todo, doing, done, completion = row
                print(f"  Vx: {vxType}")
                print(f"  維度: {plant}-{factory}-{line}")
                print(f"  工單號: {moNumber}")
                print(f"  TaskDefKey: {taskDefKey}")
                print(f"  任務統計: 總={total}, TODO={todo}, DOING={doing}, DONE={done}, 完成率={completion}%")
                print(f"  ---")
        else:
            print("  無符合條件的 V3 資料")
            
        # 額外測試：檢查是否有任何 2025-12-25 的資料
        print("\n=== 檢查 2025-12-25 是否有任何資料 ===")
        check_sql = """
        SELECT COUNT(*) as total_tasks
        FROM ACT_HI_PROCINST hi 
        LEFT JOIN ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_ 
        WHERE ( hti.START_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
                OR hti.CLAIM_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
                OR hti.END_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59' )
        """
        
        cursor.execute(check_sql)
        total_count = cursor.fetchone()[0]
        print(f"2025-12-25 總任務數: {total_count}")
        
        # 檢查 Vx 分佈
        print("\n=== 檢查 2025-12-25 Vx 分佈 ===")
        vx_dist_sql = """
        SELECT 
            CASE 
                WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%'
                     OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%'
                     OR var_moNumber.TEXT_ LIKE '315%'
                THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                ELSE SUBSTRING(hti.TASK_DEF_KEY_, 1, 2)
            END as vxType,
            COUNT(*) as count
        FROM ACT_HI_PROCINST hi 
        LEFT JOIN ACT_HI_VARINST var_moNumber on hi.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ and var_moNumber.NAME_ = 'moNumber' 
        LEFT JOIN ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_ 
        WHERE ( hti.START_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
                OR hti.CLAIM_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
                OR hti.END_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59' )
        GROUP BY 
            CASE 
                WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%'
                     OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%'
                     OR var_moNumber.TEXT_ LIKE '315%'
                THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                ELSE SUBSTRING(hti.TASK_DEF_KEY_, 1, 2)
            END
        ORDER BY count DESC
        """
        
        cursor.execute(vx_dist_sql)
        vx_results = cursor.fetchall()
        
        for vx_type, count in vx_results:
            print(f"  {vx_type}: {count} 個任務")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ 查詢失敗: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函數"""
    print("=" * 80)
    print("測試 MSSQL Vx 歸屬邏輯")
    print("=" * 80)
    print(f"執行時間: {datetime.now()}")
    print()
    
    test_vx_logic()

if __name__ == "__main__":
    main()