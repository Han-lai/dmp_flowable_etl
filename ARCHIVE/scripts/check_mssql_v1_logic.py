#!/usr/bin/env python3
"""
檢查 MSSQL 中的 V1 歸屬邏輯
確認是否有條件缺失導致無法獲得期望結果
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

def check_v1_logic_conditions():
    """檢查 V1 歸屬邏輯的各種條件"""
    print("=" * 80)
    print("檢查 MSSQL 中的 V1 歸屬邏輯條件")
    print("=" * 80)
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 檢查 WJ2+NBU+E5 在指定日期的所有任務
        dates = ['2025-12-28', '2025-12-30', '2025-12-31']
        
        for date in dates:
            print(f"\n{'='*60}")
            print(f"檢查 {date} WJ2+NBU+E5 的任務")
            print(f"{'='*60}")
            
            # 1. 檢查所有任務的 TaskDefinitionKey 和 moNumber
            detail_sql = f"""
            SELECT 
                hti.ID_ as task_id,
                hti.TASK_DEF_KEY_ as task_definition_key,
                var_moNumber.TEXT_ as mo_number,
                CASE
                    WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                    WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                    ELSE 'TODO'
                END AS task_status,
                -- 原始邏輯 (工單號優先)
                CASE 
                    WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                      OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                      OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                    ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                END as vx_type_old,
                -- 修正邏輯 (TaskDefinitionKey 優先)
                CASE 
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                    WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                      OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                      OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                    ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                END as vx_type_new
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
              AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
            ORDER BY hti.TASK_DEF_KEY_, var_moNumber.TEXT_
            """
            
            cursor.execute(detail_sql)
            results = cursor.fetchall()
            
            if results:
                print(f"\n{date} 任務詳細:")
                print(f"{'TaskId':<15} {'DefKey':<15} {'MoNumber':<12} {'Status':<8} {'Old_VX':<8} {'New_VX':<8}")
                print("-" * 85)
                
                for row in results:
                    task_id, def_key, mo_number, status, old_vx, new_vx = row
                    print(f"{task_id[:15]:<15} {def_key:<15} {mo_number or 'NULL':<12} {status:<8} {old_vx:<8} {new_vx:<8}")
                
                # 2. 統計兩種邏輯的結果
                print(f"\n{date} 統計結果:")
                
                summary_sql = f"""
                WITH task_with_vx AS (
                    SELECT 
                        hti.ID_ as task_id,
                        CASE
                            WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                            WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                            ELSE 'TODO'
                        END AS task_status,
                        -- 原始邏輯
                        CASE 
                            WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                              OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                              OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                            ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                        END as vx_type_old,
                        -- 修正邏輯
                        CASE 
                            WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                            WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                            WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                            WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                              OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                              OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                            ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                        END as vx_type_new
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
                      AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
                )
                SELECT 
                    '原始邏輯' as logic_type,
                    vx_type_old as vx_type,
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_tasks,
                    SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_tasks,
                    SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_tasks
                FROM task_with_vx
                GROUP BY vx_type_old
                UNION ALL
                SELECT 
                    '修正邏輯' as logic_type,
                    vx_type_new as vx_type,
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_tasks,
                    SUM(CASE WHEN task_status = 'TODO' THEN 1 ELSE 0 END) as todo_tasks,
                    SUM(CASE WHEN task_status = 'DOING' THEN 1 ELSE 0 END) as doing_tasks
                FROM task_with_vx
                GROUP BY vx_type_new
                ORDER BY logic_type, vx_type
                """
                
                cursor.execute(summary_sql)
                summary_results = cursor.fetchall()
                
                if summary_results:
                    print(f"{'Logic':<10} {'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
                    print("-" * 50)
                    for row in summary_results:
                        logic, vx_type, total, done, todo, doing = row
                        print(f"{logic:<10} {vx_type or 'NULL':<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
            else:
                print(f"❌ {date} 無任務資料")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ MSSQL 連接失敗: {e}")

def check_v1_task_definition_keys():
    """檢查是否有真正的 V1 TaskDefinitionKey"""
    print(f"\n{'='*80}")
    print("檢查是否有真正的 V1 TaskDefinitionKey")
    print(f"{'='*80}")
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 檢查 WJ2+NBU+E5 所有日期的 TaskDefinitionKey 分布
        v1_check_sql = """
        SELECT DISTINCT
            hti.TASK_DEF_KEY_ as task_definition_key,
            COUNT(*) as task_count,
            MIN(CONVERT(DATE, hti.START_TIME_)) as min_date,
            MAX(CONVERT(DATE, hti.START_TIME_)) as max_date
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
          AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
        GROUP BY hti.TASK_DEF_KEY_
        ORDER BY task_count DESC
        """
        
        cursor.execute(v1_check_sql)
        results = cursor.fetchall()
        
        if results:
            print(f"WJ2+NBU+E5 TaskDefinitionKey 分布:")
            print(f"{'DefKey':<15} {'Count':<8} {'Min Date':<12} {'Max Date':<12} {'VX Type':<8}")
            print("-" * 65)
            
            v1_found = False
            for row in results:
                def_key, count, min_date, max_date = row
                vx_type = def_key[:2] if def_key else 'NULL'
                if def_key and def_key.startswith('V1'):
                    v1_found = True
                    marker = " ← V1!"
                else:
                    marker = ""
                print(f"{def_key:<15} {count:<8} {str(min_date):<12} {str(max_date):<12} {vx_type:<8}{marker}")
            
            if not v1_found:
                print(f"\n⚠️ 未發現任何 V1 開頭的 TaskDefinitionKey")
                print(f"   所有任務都是 V3 類型，期望的 V1 任務可能不存在")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ MSSQL 連接失敗: {e}")

def main():
    """主要執行流程"""
    print("檢查 MSSQL V1 歸屬邏輯條件")
    
    # 檢查 V1 邏輯條件
    check_v1_logic_conditions()
    
    # 檢查是否有真正的 V1 TaskDefinitionKey
    check_v1_task_definition_keys()
    
    print(f"\n{'='*80}")
    print("結論")
    print(f"{'='*80}")
    print("1. 如果期望結果中有 V1 任務，但實際 MSSQL 中都是 V3 TaskDefinitionKey")
    print("2. 那麼期望結果可能基於錯誤的 V1 歸屬邏輯 (工單號優先)")
    print("3. 修正後的邏輯 (TaskDefinitionKey 優先) 是正確的")
    print("4. 應該以修正後的邏輯結果為準")

if __name__ == "__main__":
    main()