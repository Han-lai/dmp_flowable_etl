#!/usr/bin/env python3
"""
找出缺失的 V1 條件
對比期望結果與實際結果，找出可能的篩選條件差異
"""
import pymssql

# MSSQL 連接設定
MSSQL_SERVER = "twtpesqldv2.delta.corp"
MSSQL_PORT = "1433"
MSSQL_USER = "DMP_APP_SRV"
MSSQL_PASSWORD = "APP@DB#01"
MSSQL_DATABASE = "APP_SRV_BPM"

def get_mssql_connection():
    """建立 MSSQL 連線"""
    return pymssql.connect(
        server=MSSQL_SERVER,
        port=MSSQL_PORT,
        user=MSSQL_USER,
        password=MSSQL_PASSWORD,
        database=MSSQL_DATABASE
    )

def check_bypass_conditions():
    """檢查不同 bypass 條件的影響"""
    print("=" * 80)
    print("檢查不同 bypass 條件的影響")
    print("=" * 80)
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        dates = ['2025-12-30', '2025-12-31']
        
        for date in dates:
            print(f"\n{'-'*60}")
            print(f"檢查 {date} 不同 bypass 條件")
            print(f"{'-'*60}")
            
            # 檢查包含 bypass 任務的情況
            bypass_sql = f"""
            SELECT 
                CASE WHEN var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0 THEN 'N' ELSE 'Y' END as bypass_status,
                COUNT(*) as task_count,
                SUM(CASE WHEN hti.END_TIME_ IS NOT NULL THEN 1 ELSE 0 END) as done_count,
                SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NOT NULL THEN 1 ELSE 0 END) as doing_count,
                SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NULL THEN 1 ELSE 0 END) as todo_count
            FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
            INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
            LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
            WHERE var_plant.TEXT_ = 'WJ2' 
              AND var_factory.TEXT_ = 'NBU' 
              AND var_lineName.TEXT_ = 'E5'
              AND CONVERT(DATE, hti.START_TIME_) = '{date}'
            GROUP BY CASE WHEN var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0 THEN 'N' ELSE 'Y' END
            ORDER BY bypass_status
            """
            
            cursor.execute(bypass_sql)
            results = cursor.fetchall()
            
            print(f"{'Bypass':<8} {'Total':<6} {'Done':<6} {'DOING':<6} {'TODO':<6}")
            print("-" * 40)
            
            total_all = 0
            for row in results:
                bypass_status, task_count, done_count, doing_count, todo_count = row
                total_all += task_count
                print(f"{bypass_status:<8} {task_count:<6} {done_count:<6} {doing_count:<6} {todo_count:<6}")
            
            print(f"{'ALL':<8} {total_all:<6}")
            
            # 檢查 bypass=Y 的任務詳細
            if total_all > 7:  # 如果總數超過我們之前看到的數量
                print(f"\n{date} bypass=Y 任務詳細:")
                bypass_detail_sql = f"""
                SELECT 
                    hti.TASK_DEF_KEY_ as task_definition_key,
                    var_moNumber.TEXT_ as mo_number,
                    CASE
                        WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                        WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                        ELSE 'TODO'
                    END AS task_status,
                    COUNT(*) as task_count
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
                  AND CONVERT(DATE, hti.START_TIME_) = '{date}'
                  AND var_bypass.LONG_ = 1
                GROUP BY hti.TASK_DEF_KEY_, var_moNumber.TEXT_, 
                         CASE WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                              WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                              ELSE 'TODO' END
                ORDER BY task_count DESC
                """
                
                cursor.execute(bypass_detail_sql)
                bypass_results = cursor.fetchall()
                
                if bypass_results:
                    print(f"{'DefKey':<15} {'MoNumber':<12} {'Status':<8} {'Count':<6}")
                    print("-" * 50)
                    for row in bypass_results:
                        def_key, mo_number, status, count = row
                        print(f"{def_key:<15} {mo_number or 'NULL':<12} {status:<8} {count:<6}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ MSSQL 連接失敗: {e}")

def check_different_date_ranges():
    """檢查不同日期範圍的任務"""
    print(f"\n{'='*80}")
    print("檢查不同日期範圍的任務")
    print(f"{'='*80}")
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 檢查 2025-12-28 到 2025-12-31 的所有任務
        date_range_sql = """
        SELECT 
            CONVERT(DATE, hti.START_TIME_) as task_date,
            COUNT(*) as total_tasks,
            SUM(CASE WHEN hti.END_TIME_ IS NOT NULL THEN 1 ELSE 0 END) as done_tasks,
            SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NOT NULL THEN 1 ELSE 0 END) as doing_tasks,
            SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NULL THEN 1 ELSE 0 END) as todo_tasks,
            -- 不同 bypass 條件的統計
            SUM(CASE WHEN var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0 THEN 1 ELSE 0 END) as non_bypass_tasks,
            SUM(CASE WHEN var_bypass.LONG_ = 1 THEN 1 ELSE 0 END) as bypass_tasks
        FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
        INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
        WHERE var_plant.TEXT_ = 'WJ2' 
          AND var_factory.TEXT_ = 'NBU' 
          AND var_lineName.TEXT_ = 'E5'
          AND CONVERT(DATE, hti.START_TIME_) BETWEEN '2025-12-28' AND '2025-12-31'
        GROUP BY CONVERT(DATE, hti.START_TIME_)
        ORDER BY task_date
        """
        
        cursor.execute(date_range_sql)
        results = cursor.fetchall()
        
        print(f"{'Date':<12} {'Total':<6} {'Done':<6} {'DOING':<6} {'TODO':<6} {'NonBypass':<10} {'Bypass':<8}")
        print("-" * 70)
        
        for row in results:
            task_date, total, done, doing, todo, non_bypass, bypass = row
            print(f"{str(task_date):<12} {total:<6} {done:<6} {doing:<6} {todo:<6} {non_bypass:<10} {bypass:<8}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ MSSQL 連接失敗: {e}")

def check_v1_attribution_with_bypass():
    """檢查包含 bypass 任務的 V1 歸屬"""
    print(f"\n{'='*80}")
    print("檢查包含 bypass 任務的 V1 歸屬")
    print(f"{'='*80}")
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        dates = ['2025-12-30', '2025-12-31']
        
        for date in dates:
            print(f"\n{'-'*60}")
            print(f"檢查 {date} 包含 bypass 任務的 V1 歸屬")
            print(f"{'-'*60}")
            
            # 使用期望結果的邏輯：工單號優先，包含 bypass 任務
            v1_with_bypass_sql = f"""
            SELECT 
                -- 原始邏輯 (工單號優先，包含 bypass)
                CASE 
                    WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                      OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                      OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                    ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                END as vx_type,
                COUNT(*) as total_tasks,
                SUM(CASE WHEN hti.END_TIME_ IS NOT NULL THEN 1 ELSE 0 END) as done_tasks,
                SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NULL THEN 1 ELSE 0 END) as todo_tasks,
                SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NOT NULL THEN 1 ELSE 0 END) as doing_tasks
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
              AND CONVERT(DATE, hti.START_TIME_) = '{date}'
              -- 不排除 bypass 任務
            GROUP BY CASE 
                WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                  OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                  OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                ELSE LEFT(hti.TASK_DEF_KEY_, 2)
            END
            ORDER BY vx_type
            """
            
            cursor.execute(v1_with_bypass_sql)
            results = cursor.fetchall()
            
            print(f"包含 bypass 任務的結果 (工單號優先邏輯):")
            print(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
            print("-" * 35)
            
            for row in results:
                vx_type, total, done, todo, doing = row
                print(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ MSSQL 連接失敗: {e}")

def main():
    """主要執行流程"""
    print("找出缺失的 V1 條件")
    
    # 1. 檢查 bypass 條件的影響
    check_bypass_conditions()
    
    # 2. 檢查不同日期範圍
    check_different_date_ranges()
    
    # 3. 檢查包含 bypass 任務的 V1 歸屬
    check_v1_attribution_with_bypass()
    
    print(f"\n{'='*80}")
    print("分析結論")
    print(f"{'='*80}")
    print("期望結果可能的來源:")
    print("1. 包含了 bypass=Y 的任務 (autoComplete=1)")
    print("2. 使用了工單號優先的 V1 歸屬邏輯")
    print("3. 可能包含了不同日期範圍的任務")
    print("4. 可能使用了不同的篩選條件")

if __name__ == "__main__":
    main()