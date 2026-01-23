#!/usr/bin/env python3
"""
驗證 CNE WJ2 NBU E5 V3 條件下 2025-12-25 的 L5 指標
比較 MSSQL、ClickHouse 和 Cube.js 的數據一致性

條件：
- Region: CNE
- Factory: WJ2  
- Plant: NBU
- Line: E5
- Vx Type: V3
- Date: 2025-12-25

注意：根據之前的維度對應修正：
- MSSQL 中的 plant=NBU 對應 ClickHouse 中的 plant_code=NBU
- MSSQL 中的 factory=WJ2 對應 ClickHouse 中的 factory_code=WJ2
"""

import pyodbc
import clickhouse_connect
import requests
import json
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

def connect_clickhouse():
    """連接 ClickHouse"""
    return clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )

def query_mssql_l5_metrics():
    """查詢 MSSQL L5 指標"""
    print("=== 查詢 MSSQL L5 指標 ===")
    
    conn = connect_mssql()
    if not conn:
        print("❌ MSSQL 連線失敗")
        return []
    cursor = conn.cursor()
    
    # 使用您提供的正確查詢格式
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
      AND var_plant.TEXT_ = 'NBU'
      AND var_factory.TEXT_ = 'WJ2'
      AND var_lineName.TEXT_ = 'E5'
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
        var_lineName.TEXT_
    """
    
    cursor.execute(sql)
    results = cursor.fetchall()
    
    print("MSSQL 查詢結果:")
    if results:
        for row in results:
            print(f"  Vx: {row[0]}, Plant: {row[1]}, Factory: {row[2]}, Line: {row[3]}")
            print(f"  總任務: {row[4]}, TODO: {row[5]}, DOING: {row[6]}, DONE: {row[7]}")
            print(f"  完成率: {row[8]}%")
    else:
        print("  無符合條件的資料")
    
    cursor.close()
    conn.close()
    
    return results

def query_clickhouse_l5_metrics():
    """查詢 ClickHouse L5 指標"""
    print("\n=== 查詢 ClickHouse L5 指標 ===")
    
    client = connect_clickhouse()
    
    # 查詢 Silver 層原始資料
    print("1. Silver 層原始資料:")
    sql_silver = """
    SELECT 
        vx_type,
        region_code,
        plant_code,
        factory_code,
        line_code,
        COUNT(*) as total_tasks,
        countIf(task_status = 'TODO') as todo_tasks,
        countIf(task_status = 'DOING') as doing_tasks,
        countIf(task_status = 'DONE') as done_tasks,
        CASE 
            WHEN COUNT(*) > 0 
            THEN ROUND(countIf(task_status = 'DONE') * 100.0 / COUNT(*), 2)
            ELSE 0.0
        END as completion_rate
    FROM silver.mv_fact_task_vx_attribution_mdm
    WHERE task_create_date = '2025-12-25'
      AND vx_type = 'V3'
      AND region_code = 'CNE'
      AND plant_code = 'NBU'
      AND factory_code = 'WJ2'
      AND line_code = 'E5'
      AND is_excluded = 0
    GROUP BY vx_type, region_code, plant_code, factory_code, line_code
    """
    
    try:
        result = client.query(sql_silver)
        if result.result_rows:
            for row in result.result_rows:
                print(f"  Vx: {row[0]}, Region: {row[1]}, Plant: {row[2]}, Factory: {row[3]}, Line: {row[4]}")
                print(f"  總任務: {row[5]}, TODO: {row[6]}, DOING: {row[7]}, DONE: {row[8]}")
                print(f"  完成率: {row[9]}%")
        else:
            print("  Silver 層無符合條件的資料")
    except Exception as e:
        print(f"  Silver 層查詢失敗: {e}")
    
    # 查詢 Gold 層聚合資料
    print("\n2. Gold 層聚合資料:")
    sql_gold = """
    SELECT 
        vx_type,
        region_code,
        plant_code,
        factory_code,
        line_code,
        sum_total_task_qty,
        sum_todo_qty,
        sum_doing_qty,
        sum_done_qty,
        completion_rate
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
    WHERE snapshot_date = '2025-12-25'
      AND vx_type = 'V3'
      AND region_code = 'CNE'
      AND plant_code = 'NBU'
      AND factory_code = 'WJ2'
      AND line_code = 'E5'
    """
    
    try:
        result = client.query(sql_gold)
        if result.result_rows:
            for row in result.result_rows:
                print(f"  Vx: {row[0]}, Region: {row[1]}, Plant: {row[2]}, Factory: {row[3]}, Line: {row[4]}")
                print(f"  總任務: {row[5]}, TODO: {row[6]}, DOING: {row[7]}, DONE: {row[8]}")
                print(f"  完成率: {row[9]}%")
        else:
            print("  Gold 層無符合條件的資料")
    except Exception as e:
        print(f"  Gold 層查詢失敗: {e}")
    
    return result.result_rows if 'result' in locals() and result.result_rows else []

def query_cubejs_l5_metrics():
    """查詢 Cube.js L5 指標"""
    print("\n=== 查詢 Cube.js L5 指標 ===")
    
    # Cube.js API 查詢（簡化版本）
    cube_query = {
        "measures": [
            "GoldL5TaskCompletion.totalTasks",
            "GoldL5TaskCompletion.todoTasks", 
            "GoldL5TaskCompletion.doingTasks",
            "GoldL5TaskCompletion.doneTasks",
            "GoldL5TaskCompletion.completionRate"
        ],
        "dimensions": [
            "GoldL5TaskCompletion.vxType",
            "GoldL5TaskCompletion.plant",
            "GoldL5TaskCompletion.factory",
            "GoldL5TaskCompletion.line"
        ],
        "filters": [
            {
                "member": "GoldL5TaskCompletion.snapshotDate",
                "operator": "equals",
                "values": ["2025-12-25"]
            },
            {
                "member": "GoldL5TaskCompletion.vxType",
                "operator": "equals", 
                "values": ["V3"]
            },
            {
                "member": "GoldL5TaskCompletion.plant",
                "operator": "equals",
                "values": ["NBU"]
            },
            {
                "member": "GoldL5TaskCompletion.factory",
                "operator": "equals",
                "values": ["WJ2"]
            },
            {
                "member": "GoldL5TaskCompletion.line",
                "operator": "equals",
                "values": ["E5"]
            }
        ]
    }
    
    try:
        # 使用正確的 Cube.js API 端點
        cube_api_url = "http://10.136.218.207:4002/cubejs-api/v1/load"
        
        headers = {
            "Content-Type": "application/json",
            # "Authorization": "Bearer YOUR_TOKEN"  # 如果需要認證
        }
        
        response = requests.post(
            cube_api_url,
            headers=headers,
            json={"query": cube_query},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("data"):
                print("Cube.js 查詢結果:")
                for row in data["data"]:
                    print(f"  Vx: {row.get('GoldL5TaskCompletion.vxType', 'N/A')}")
                    print(f"  Plant: {row.get('GoldL5TaskCompletion.plant', 'N/A')}")
                    print(f"  Factory: {row.get('GoldL5TaskCompletion.factory', 'N/A')}")
                    print(f"  Line: {row.get('GoldL5TaskCompletion.line', 'N/A')}")
                    print(f"  總任務: {row.get('GoldL5TaskCompletion.totalTasks', 0)}")
                    print(f"  TODO: {row.get('GoldL5TaskCompletion.todoTasks', 0)}")
                    print(f"  DOING: {row.get('GoldL5TaskCompletion.doingTasks', 0)}")
                    print(f"  DONE: {row.get('GoldL5TaskCompletion.doneTasks', 0)}")
                    print(f"  完成率: {row.get('GoldL5TaskCompletion.completionRate', 0)}%")
            else:
                print("  Cube.js 無符合條件的資料")
        else:
            print(f"  Cube.js API 請求失敗: {response.status_code}")
            print(f"  錯誤訊息: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("  Cube.js API 連線失敗 (可能服務未啟動)")
        print("  請確認 Cube.js 服務是否在 http://localhost:4000 運行")
    except Exception as e:
        print(f"  Cube.js 查詢失敗: {e}")

def main():
    """主函數"""
    print("=" * 80)
    print("驗證 CNE WJ2 NBU E5 V3 條件下 2025-12-25 的 L5 指標")
    print("=" * 80)
    print(f"執行時間: {datetime.now()}")
    print()
    
    print("查詢條件:")
    print("  Region: CNE")
    print("  Factory: WJ2")
    print("  Plant: NBU") 
    print("  Line: E5")
    print("  Vx Type: V3")
    print("  Date: 2025-12-25")
    print()
    
    # 查詢各個資料源
    try:
        mssql_results = query_mssql_l5_metrics()
        clickhouse_results = query_clickhouse_l5_metrics()
        query_cubejs_l5_metrics()
        
        # 比較結果
        print("\n" + "=" * 80)
        print("結果比較")
        print("=" * 80)
        
        if mssql_results:
            mssql_row = mssql_results[0]
            print(f"MSSQL    - 總任務: {mssql_row[4]}, 完成率: {mssql_row[8]}%")
        else:
            print("MSSQL    - 無資料")
            
        if clickhouse_results:
            ch_row = clickhouse_results[0]
            print(f"ClickHouse - 總任務: {ch_row[5]}, 完成率: {ch_row[9]}%")
        else:
            print("ClickHouse - 無資料")
            
        print("Cube.js  - 請參考上方查詢結果")
        
        # 一致性檢查
        if mssql_results and clickhouse_results:
            mssql_total = mssql_results[0][4]
            ch_total = clickhouse_results[0][5]
            mssql_rate = mssql_results[0][8]
            ch_rate = clickhouse_results[0][9]
            
            print(f"\n一致性檢查:")
            print(f"  總任務數一致: {'✅' if mssql_total == ch_total else '❌'} (MSSQL: {mssql_total}, ClickHouse: {ch_total})")
            print(f"  完成率一致: {'✅' if abs(mssql_rate - ch_rate) < 0.01 else '❌'} (MSSQL: {mssql_rate}%, ClickHouse: {ch_rate}%)")
        
    except Exception as e:
        print(f"執行失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()