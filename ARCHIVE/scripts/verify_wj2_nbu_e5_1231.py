#!/usr/bin/env python3
"""
驗證 WJ2+NBU+E5 2025-12-31 的數值
對比 MSSQL 原始資料與 ClickHouse 資料
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
    print("ClickHouse 資料檢查 - WJ2+NBU+E5 2025-12-31")
    print("=" * 80)
    
    client = get_clickhouse_client()
    
    # 1. 檢查 Gold 層 2025-12-31 當天資料
    print("\n1. Gold 層 2025-12-31 當天資料...")
    
    gold_daily_sql = """
    SELECT 
        vx_type,
        time_period_type,
        time_period_value,
        total_task_qty,
        done_qty,
        done_pct,
        _snapshot_time
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND snapshot_date = '2025-12-31'
    ORDER BY time_period_type, vx_type
    """
    
    result = client.query(gold_daily_sql)
    if result.result_rows:
        print(f"  {'VX':<4} {'Type':<8} {'Value':<12} {'Total':<8} {'Done':<8} {'%':<8} {'Time':<20}")
        print("  " + "-" * 75)
        for row in result.result_rows:
            vx_type, period_type, value, total, done, pct, time = row
            print(f"  {vx_type:<4} {period_type:<8} {value:<12} {total:<8} {done:<8} {pct:<8.1f} {str(time)[:19]}")
    else:
        print("  ❌ 無 2025-12-31 Gold 層資料")
    
    # 2. 檢查 Silver 層 2025-12-31 當天資料
    print("\n2. Silver 層 2025-12-31 當天資料...")
    
    silver_daily_sql = """
    SELECT 
        vx_type,
        COUNT(*) as total_tasks,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_tasks,
        SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_tasks,
        SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_tasks
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND task_create_date = '2025-12-31'
      AND is_excluded = 0
    GROUP BY vx_type
    ORDER BY vx_type
    """
    
    result = client.query(silver_daily_sql)
    if result.result_rows:
        print(f"  {'VX':<4} {'Total':<8} {'Done':<8} {'TODO':<8} {'DOING':<8} {'Done %':<8}")
        print("  " + "-" * 50)
        
        total_all = 0
        done_all = 0
        for row in result.result_rows:
            vx_type, total, done, todo, doing = row
            total_all += total
            done_all += done
            done_pct = (done * 100.0 / total) if total > 0 else 0
            print(f"  {vx_type:<4} {total:<8} {done:<8} {todo:<8} {doing:<8} {done_pct:<8.1f}")
        
        print(f"  {'ALL':<4} {total_all:<8} {done_all:<8} {'':<8} {'':<8} {(done_all * 100.0 / total_all) if total_all > 0 else 0:<8.1f}")
    else:
        print("  ❌ 無 2025-12-31 Silver 層資料")
    
    # 3. 檢查 Silver 層任務詳細資訊
    print("\n3. Silver 層 2025-12-31 任務詳細資訊...")
    
    silver_detail_sql = """
    SELECT 
        vx_type,
        task_definition_key,
        mo_number,
        task_status,
        COUNT(*) as task_count
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND task_create_date = '2025-12-31'
      AND is_excluded = 0
    GROUP BY vx_type, task_definition_key, mo_number, task_status
    ORDER BY vx_type, task_count DESC
    """
    
    result = client.query(silver_detail_sql)
    if result.result_rows:
        print(f"  {'VX':<4} {'DefKey':<15} {'MoNumber':<12} {'Status':<8} {'Count':<6}")
        print("  " + "-" * 55)
        for row in result.result_rows:
            vx_type, def_key, mo_number, status, count = row
            print(f"  {vx_type:<4} {def_key:<15} {mo_number or 'NULL':<12} {status:<8} {count:<6}")
    else:
        print("  ❌ 無任務詳細資料")

def check_mssql_data():
    """檢查 MSSQL 原始資料"""
    print("\n" + "=" * 80)
    print("MSSQL 原始資料檢查 - WJ2+NBU+E5 2025-12-31")
    print("=" * 80)
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 1. 檢查 2025-12-31 原始任務資料
        print("\n1. 2025-12-31 原始任務資料...")
        
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
          AND CONVERT(DATE, hti.START_TIME_) = '2025-12-31'
          AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
        """
        
        cursor.execute(raw_task_sql)
        result = cursor.fetchone()
        if result:
            total, done, doing, todo = result
            print(f"  總任務: {total}, Done任務: {done}, DOING任務: {doing}, TODO任務: {todo}")
            if total > 0:
                print(f"  完成率: {done * 100.0 / total:.2f}%")
        
        # 2. 檢查 2025-12-31 Vx 歸屬邏輯
        print("\n2. 2025-12-31 Vx 歸屬邏輯...")
        
        vx_logic_sql = """
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
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
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
              AND CONVERT(DATE, hti.START_TIME_) = '2025-12-31'
              AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
        )
        SELECT 
            vx_type,
            COUNT(*) as total_tasks,
            SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_tasks,
            SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_tasks,
            SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_tasks
        FROM task_with_vx
        GROUP BY vx_type
        ORDER BY vx_type
        """
        
        cursor.execute(vx_logic_sql)
        results = cursor.fetchall()
        if results:
            print(f"  {'VX Type':<8} {'Total':<8} {'Done':<8} {'TODO':<8} {'DOING':<8} {'Done %':<8}")
            print("  " + "-" * 60)
            
            total_all = 0
            done_all = 0
            for row in results:
                vx_type, total, done, todo, doing = row
                total_all += total
                done_all += done
                done_pct = (done * 100.0 / total) if total > 0 else 0
                print(f"  {vx_type or 'NULL':<8} {total:<8} {done:<8} {todo:<8} {doing:<8} {done_pct:<8.1f}")
            
            print(f"  {'ALL':<8} {total_all:<8} {done_all:<8} {'':<8} {'':<8} {(done_all * 100.0 / total_all) if total_all > 0 else 0:<8.1f}")
        
        # 3. 檢查任務詳細分布
        print("\n3. 2025-12-31 任務詳細分布...")
        
        detail_sql = """
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
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
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
              AND CONVERT(DATE, hti.START_TIME_) = '2025-12-31'
              AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
        )
        SELECT 
            vx_type,
            task_definition_key,
            mo_number,
            task_status,
            COUNT(*) as task_count
        FROM task_with_vx
        GROUP BY vx_type, task_definition_key, mo_number, task_status
        ORDER BY vx_type, task_count DESC
        """
        
        cursor.execute(detail_sql)
        results = cursor.fetchall()
        if results:
            print(f"  {'VX':<4} {'DefKey':<15} {'MoNumber':<12} {'Status':<8} {'Count':<6}")
            print("  " + "-" * 55)
            for row in results:
                vx_type, def_key, mo_number, status, count = row
                print(f"  {vx_type or 'NULL':<4} {def_key:<15} {mo_number or 'NULL':<12} {status:<8} {count:<6}")
        else:
            print("  ❌ 無任務詳細資料")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ MSSQL 連接失敗: {e}")

def compare_results():
    """比較結果"""
    print("\n" + "=" * 80)
    print("結果比較與分析")
    print("=" * 80)
    
    print("\n🔍 數據一致性檢查:")
    print("1. 檢查 MSSQL 與 ClickHouse Silver 層數據是否一致")
    print("2. 檢查 Silver 層與 Gold 層數據是否一致")
    print("3. 驗證 V1 歸屬邏輯修正是否正確")
    
    print("\n💡 重點關注:")
    print("- V1 任務數量是否合理")
    print("- V3 任務是否正確歸類")
    print("- 總任務數是否匹配")
    print("- 完成率計算是否正確")

def main():
    """主要執行流程"""
    print("WJ2+NBU+E5 2025-12-31 數值驗證")
    print("對比 MSSQL 原始資料與 ClickHouse 資料")
    
    # 檢查 ClickHouse 資料
    check_clickhouse_data()
    
    # 檢查 MSSQL 資料
    check_mssql_data()
    
    # 比較結果
    compare_results()

if __name__ == "__main__":
    main()