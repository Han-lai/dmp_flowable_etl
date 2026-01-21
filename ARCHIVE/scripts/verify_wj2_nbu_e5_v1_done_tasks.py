#!/usr/bin/env python3
"""
驗證 WJ2+NBU+E5+V1 的 done task 數量
對比 MSSQL 原始資料與 ClickHouse Gold 層資料
"""
import clickhouse_connect
import pymssql

# ClickHouse 連接設定
CH_HOST = "10.136.218.207"
CH_PORT = 8121
CH_USER = "default"
CH_PASSWORD = "default"

# MSSQL 連接設定
MSSQL_SERVER = "twtpesqldv2.delta.corp"
MSSQL_PORT = "1433"
MSSQL_USER = "DMP_APP_SRV"
MSSQL_PASSWORD = "APP@DB#01"
MSSQL_DATABASE = "APP_SRV_BPM"

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD
    )

def get_mssql_connection():
    """建立 MSSQL 連線"""
    return pymssql.connect(
        server=MSSQL_SERVER,
        port=MSSQL_PORT,
        user=MSSQL_USER,
        password=MSSQL_PASSWORD,
        database=MSSQL_DATABASE
    )

def check_clickhouse_data():
    """檢查 ClickHouse 中的資料"""
    print("=" * 80)
    print("ClickHouse 資料檢查")
    print("=" * 80)
    
    client = get_clickhouse_client()
    
    # 1. 檢查 Gold 層 2025-12-28 當天資料
    print("\n1. Gold 層 2025-12-28 當天資料...")
    
    gold_daily_sql = """
    SELECT 
        time_period_type,
        time_period_value,
        total_task_qty,
        done_qty,
        done_pct,
        _snapshot_time
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND snapshot_date = '2025-12-28'
    ORDER BY time_period_type
    """
    
    result = client.query(gold_daily_sql)
    if result.result_rows:
        print(f"  {'Type':<8} {'Value':<12} {'Total':<8} {'Done':<8} {'%':<8} {'Time':<20}")
        print("  " + "-" * 70)
        for row in result.result_rows:
            period_type, value, total, done, pct, time = row
            print(f"  {period_type:<8} {value:<12} {total:<8} {done:<8} {pct:<8} {str(time)[:19]}")
    else:
        print("  ❌ 無 2025-12-28 資料")
    
    # 2. 檢查 Silver 層 2025-12-28 當天資料
    print("\n2. Silver 層 2025-12-28 當天資料...")
    
    silver_daily_sql = """
    SELECT 
        COUNT(*) as total_tasks,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_tasks,
        SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_tasks,
        SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_tasks
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND task_create_date = '2025-12-28'
      AND is_excluded = 0
    """
    
    result = client.query(silver_daily_sql)
    if result.result_rows:
        for row in result.result_rows:
            total, done, todo, doing = row
            print(f"  總任務: {total:,}, Done任務: {done:,}, TODO任務: {todo:,}, DOING任務: {doing:,}")
            if total > 0:
                print(f"  完成率: {done * 100.0 / total:.2f}%")
    
    # 3. 檢查 Silver 層任務詳細資訊
    print("\n3. Silver 層 2025-12-28 任務詳細資訊...")
    
    silver_detail_sql = """
    SELECT 
        task_id,
        task_status,
        task_definition_key,
        mo_number,
        task_create_time,
        task_end_time
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND task_create_date = '2025-12-28'
      AND is_excluded = 0
      AND task_status = 'DONE'
    ORDER BY task_create_time
    LIMIT 10
    """
    
    result = client.query(silver_detail_sql)
    if result.result_rows:
        print(f"  前10筆 DONE 任務:")
        print(f"  {'TaskId':<15} {'Status':<8} {'DefKey':<12} {'MoNumber':<12} {'CreateTime':<20}")
        print("  " + "-" * 80)
        for row in result.result_rows:
            task_id, status, def_key, mo_number, create_time, end_time = row
            print(f"  {task_id:<15} {status:<8} {def_key:<12} {mo_number or 'NULL':<12} {str(create_time)[:19]}")
    else:
        print("  ❌ 無 DONE 任務")

def check_mssql_data():
    """檢查 MSSQL 原始資料"""
    print("\n" + "=" * 80)
    print("MSSQL 原始資料檢查")
    print("=" * 80)
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 1. 檢查 2025-12-28 原始任務資料
        print("\n1. 2025-12-28 原始任務資料...")
        
        raw_task_sql = """
        SELECT 
            COUNT(*) as total_tasks,
            SUM(CASE WHEN hti.END_TIME_ IS NOT NULL THEN 1 ELSE 0 END) as done_tasks,
            SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NOT NULL THEN 1 ELSE 0 END) as doing_tasks,
            SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NULL THEN 1 ELSE 0 END) as todo_tasks
        FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
        INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
        WHERE var_plant.TEXT_ = 'WJ2' 
          AND var_factory.TEXT_ = 'NBU' 
          AND var_lineName.TEXT_ = 'E5'
          AND CONVERT(DATE, hti.START_TIME_) = '2025-12-28'
          AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
        """
        
        cursor.execute(raw_task_sql)
        result = cursor.fetchone()
        if result:
            total, done, doing, todo = result
            print(f"  總任務: {total}, Done任務: {done}, DOING任務: {doing}, TODO任務: {todo}")
            if total > 0:
                print(f"  完成率: {done * 100.0 / total:.2f}%")
        
        # 2. 檢查 2025-12-28 V1 歸屬邏輯
        print("\n2. 2025-12-28 V1 歸屬邏輯...")
        
        v1_logic_sql = """
        WITH task_with_vx AS (
            SELECT 
                hti.ID_ as task_id,
                CASE
                    WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                    WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                    ELSE 'TODO'
                END AS task_status,
                hti.TASK_DEF_KEY_ as task_definition_key,
                var_moNumber.TEXT_ as mo_number,
                CASE 
                    WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                      OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                      OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                    ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                END as vx_type
            FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
            INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber ON hi.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ AND var_moNumber.NAME_ = 'moNumber'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
            WHERE var_plant.TEXT_ = 'WJ2' 
              AND var_factory.TEXT_ = 'NBU' 
              AND var_lineName.TEXT_ = 'E5'
              AND CONVERT(DATE, hti.START_TIME_) = '2025-12-28'
              AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
        )
        SELECT 
            vx_type,
            COUNT(*) as total_tasks,
            SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_tasks
        FROM task_with_vx
        GROUP BY vx_type
        ORDER BY vx_type
        """
        
        cursor.execute(v1_logic_sql)
        results = cursor.fetchall()
        if results:
            print(f"  {'VX Type':<8} {'Total':<8} {'Done':<8}")
            print("  " + "-" * 25)
            for row in results:
                vx_type, total, done = row
                print(f"  {vx_type or 'NULL':<8} {total:<8} {done:<8}")
        
        # 3. 檢查 2025-12-28 V1 的詳細資料
        print("\n3. 2025-12-28 V1 任務詳細分析...")
        
        v1_detail_sql = """
        WITH task_with_vx AS (
            SELECT 
                hti.ID_ as task_id,
                CASE
                    WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                    WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                    ELSE 'TODO'
                END AS task_status,
                hti.TASK_DEF_KEY_ as task_definition_key,
                var_moNumber.TEXT_ as mo_number,
                hti.START_TIME_,
                hti.END_TIME_,
                CASE 
                    WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                      OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                      OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                    ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                END as vx_type
            FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
            INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber ON hi.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ AND var_moNumber.NAME_ = 'moNumber'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
            WHERE var_plant.TEXT_ = 'WJ2' 
              AND var_factory.TEXT_ = 'NBU' 
              AND var_lineName.TEXT_ = 'E5'
              AND CONVERT(DATE, hti.START_TIME_) = '2025-12-28'
              AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
        )
        SELECT 
            COUNT(*) as total_v1_tasks,
            SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_v1_tasks,
            SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_v1_tasks,
            SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_v1_tasks
        FROM task_with_vx
        WHERE vx_type = 'V1'
        """
        
        cursor.execute(v1_detail_sql)
        result = cursor.fetchone()
        if result:
            total, done, todo, doing = result
            print(f"  V1 總任務: {total}")
            print(f"  V1 Done任務: {done}")
            print(f"  V1 TODO任務: {todo}")
            print(f"  V1 DOING任務: {doing}")
            if total > 0:
                print(f"  V1 完成率: {done * 100.0 / total:.2f}%")
        
        # 4. 檢查 V1 DONE 任務的詳細資訊
        print("\n4. 2025-12-28 V1 DONE 任務詳細資訊...")
        
        v1_done_detail_sql = """
        WITH task_with_vx AS (
            SELECT 
                hti.ID_ as task_id,
                CASE
                    WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                    WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                    ELSE 'TODO'
                END AS task_status,
                hti.TASK_DEF_KEY_ as task_definition_key,
                var_moNumber.TEXT_ as mo_number,
                hti.START_TIME_,
                hti.END_TIME_,
                CASE 
                    WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                      OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                      OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                    ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                END as vx_type
            FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
            INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber ON hi.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ AND var_moNumber.NAME_ = 'moNumber'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
            WHERE var_plant.TEXT_ = 'WJ2' 
              AND var_factory.TEXT_ = 'NBU' 
              AND var_lineName.TEXT_ = 'E5'
              AND CONVERT(DATE, hti.START_TIME_) = '2025-12-28'
              AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
        )
        SELECT TOP 10
            task_id,
            task_definition_key,
            mo_number,
            START_TIME_,
            END_TIME_
        FROM task_with_vx
        WHERE vx_type = 'V1' AND task_status = 'DONE'
        ORDER BY START_TIME_
        """
        
        cursor.execute(v1_done_detail_sql)
        results = cursor.fetchall()
        if results:
            print(f"  前10筆 V1 DONE 任務:")
            print(f"  {'TaskId':<15} {'DefKey':<12} {'MoNumber':<12} {'StartTime':<20} {'EndTime':<20}")
            print("  " + "-" * 90)
            for row in results:
                task_id, def_key, mo_number, start_time, end_time = row
                print(f"  {task_id:<15} {def_key:<12} {mo_number or 'NULL':<12} {str(start_time)[:19]:<20} {str(end_time)[:19] if end_time else 'NULL':<20}")
        else:
            print("  ❌ 無 V1 DONE 任務")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ MSSQL 連接失敗: {e}")

def compare_results():
    """比較結果"""
    print("\n" + "=" * 80)
    print("結果比較與分析")
    print("=" * 80)
    
    print("\n🔍 關鍵發現:")
    print("1. ClickHouse Gold 層顯示 V1+WJ2+NBU+E5 月度 done 約 1,783 筆")
    print("2. 需要確認 MSSQL 原始資料的實際數量")
    print("3. 檢查 V1 歸屬邏輯是否正確應用")
    print("4. 驗證排除邏輯是否影響最終計數")
    
    print("\n💡 如果數量差異很大:")
    print("- 檢查 V1 歸屬規則 (moNumber 特殊規則)")
    print("- 檢查排除邏輯 (TaskBypass, TaskDefinitionKey)")
    print("- 檢查時間範圍是否一致")
    print("- 檢查資料同步是否完整")

def main():
    """主要執行流程"""
    print("WJ2+NBU+E5+V1 Done Task 數量驗證")
    print("對比 MSSQL 原始資料與 ClickHouse 資料")
    
    # 檢查 ClickHouse 資料
    check_clickhouse_data()
    
    # 檢查 MSSQL 資料
    check_mssql_data()
    
    # 比較結果
    compare_results()

if __name__ == "__main__":
    main()