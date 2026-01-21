#!/usr/bin/env python3
"""
檢查期望結果與實際結果的差異
找出可能缺失的 V1 歸屬條件
"""
import pymssql
import clickhouse_connect

# MSSQL 連接設定
MSSQL_SERVER = "twtpesqldv2.delta.corp"
MSSQL_PORT = "1433"
MSSQL_USER = "DMP_APP_SRV"
MSSQL_PASSWORD = "APP@DB#01"
MSSQL_DATABASE = "APP_SRV_BPM"

# ClickHouse 連接設定
CLICKHOUSE_HOST = "10.136.218.207"
CLICKHOUSE_PORT = 8121

def get_mssql_connection():
    """建立 MSSQL 連線"""
    return pymssql.connect(
        server=MSSQL_SERVER,
        port=MSSQL_PORT,
        user=MSSQL_USER,
        password=MSSQL_PASSWORD,
        database=MSSQL_DATABASE
    )

def get_clickhouse_connection():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT
    )

def check_expected_results():
    """檢查期望結果"""
    print("=" * 80)
    print("期望結果 (用戶提供)")
    print("=" * 80)
    
    expected_data = [
        ("2025-12-28", "V1", 0, 0, 0, 0),
        ("2025-12-28", "V3", 11, 8, 3, 0),
        ("2025-12-30", "V1", 3, 0, 3, 0),
        ("2025-12-30", "V3", 4, 0, 4, 0),
        ("2025-12-31", "V1", 12, 1, 9, 2),
        ("2025-12-31", "V1", 1, 0, 0, 1),  # 重複行？
    ]
    
    print(f"{'Date':<12} {'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
    print("-" * 50)
    
    for date, vx, total, done, todo, doing in expected_data:
        print(f"{date:<12} {vx:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
    
    return expected_data

def check_mssql_detailed_conditions():
    """檢查 MSSQL 中的詳細條件"""
    print(f"\n{'='*80}")
    print("MSSQL 詳細條件檢查")
    print(f"{'='*80}")
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        dates = ['2025-12-28', '2025-12-30', '2025-12-31']
        
        for date in dates:
            print(f"\n{'-'*60}")
            print(f"檢查 {date} 的所有可能條件")
            print(f"{'-'*60}")
            
            # 檢查所有任務，包含更多條件
            detailed_sql = f"""
            SELECT 
                hti.ID_ as task_id,
                hti.TASK_DEF_KEY_ as task_definition_key,
                var_moNumber.TEXT_ as mo_number,
                var_plant.TEXT_ as plant,
                var_factory.TEXT_ as factory,
                var_lineName.TEXT_ as line_name,
                var_bypass.LONG_ as bypass_flag,
                CASE
                    WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                    WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                    ELSE 'TODO'
                END AS task_status,
                -- 檢查各種可能的 V1 條件
                CASE WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 1 ELSE 0 END as has_v1_defkey,
                CASE WHEN var_moNumber.TEXT_ LIKE '196%' THEN 1 ELSE 0 END as has_196_mo,
                CASE WHEN var_moNumber.TEXT_ LIKE '199%' THEN 1 ELSE 0 END as has_199_mo,
                CASE WHEN var_moNumber.TEXT_ LIKE '200%' THEN 1 ELSE 0 END as has_200_mo,
                CASE WHEN var_moNumber.TEXT_ LIKE '210%' THEN 1 ELSE 0 END as has_210_mo,
                CASE WHEN var_moNumber.TEXT_ LIKE '212%' THEN 1 ELSE 0 END as has_212_mo,
                CASE WHEN var_moNumber.TEXT_ LIKE '213%' THEN 1 ELSE 0 END as has_213_mo,
                CASE WHEN var_moNumber.TEXT_ LIKE '315%' THEN 1 ELSE 0 END as has_315_mo,
                -- 檢查是否有其他變數影響
                hti.START_TIME_,
                hti.END_TIME_,
                hti.ASSIGNEE_
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
            ORDER BY hti.TASK_DEF_KEY_, var_moNumber.TEXT_
            """
            
            cursor.execute(detailed_sql)
            results = cursor.fetchall()
            
            if results:
                print(f"\n{date} 任務詳細分析:")
                print(f"{'TaskId':<15} {'DefKey':<15} {'MoNumber':<12} {'Status':<8} {'V1_DefKey':<9} {'199_Mo':<7} {'315_Mo':<7} {'Bypass':<7}")
                print("-" * 100)
                
                v1_defkey_count = 0
                v1_mo_count = 0
                
                for row in results:
                    task_id, def_key, mo_number, plant, factory, line_name, bypass_flag, status, \
                    has_v1_defkey, has_196_mo, has_199_mo, has_200_mo, has_210_mo, has_212_mo, has_213_mo, has_315_mo, \
                    start_time, end_time, assignee = row
                    
                    if has_v1_defkey:
                        v1_defkey_count += 1
                    if has_199_mo or has_315_mo:
                        v1_mo_count += 1
                    
                    print(f"{task_id[:15]:<15} {def_key:<15} {mo_number or 'NULL':<12} {status:<8} {has_v1_defkey:<9} {has_199_mo:<7} {has_315_mo:<7} {bypass_flag or 'NULL':<7}")
                
                print(f"\n{date} 統計:")
                print(f"  總任務數: {len(results)}")
                print(f"  V1 TaskDefinitionKey 任務: {v1_defkey_count}")
                print(f"  199*/315* 工單號任務: {v1_mo_count}")
                
                # 檢查是否有其他可能的 V1 條件
                other_conditions_sql = f"""
                SELECT DISTINCT
                    hti.TASK_DEF_KEY_,
                    var_moNumber.TEXT_ as mo_number,
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
                  AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
                GROUP BY hti.TASK_DEF_KEY_, var_moNumber.TEXT_
                ORDER BY task_count DESC
                """
                
                cursor.execute(other_conditions_sql)
                condition_results = cursor.fetchall()
                
                print(f"\n{date} DefKey + MoNumber 組合:")
                print(f"{'DefKey':<15} {'MoNumber':<12} {'Count':<6}")
                print("-" * 35)
                for def_key, mo_number, count in condition_results:
                    print(f"{def_key:<15} {mo_number or 'NULL':<12} {count:<6}")
            
            else:
                print(f"❌ {date} 無任務資料")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ MSSQL 連接失敗: {e}")

def check_clickhouse_current_logic():
    """檢查 ClickHouse 目前的邏輯結果"""
    print(f"\n{'='*80}")
    print("ClickHouse 目前邏輯結果")
    print(f"{'='*80}")
    
    try:
        client = get_clickhouse_connection()
        
        dates = ['2025-12-28', '2025-12-30', '2025-12-31']
        
        for date in dates:
            print(f"\n{'-'*60}")
            print(f"ClickHouse {date} 結果")
            print(f"{'-'*60}")
            
            # 檢查 Silver 層結果
            silver_sql = f"""
            SELECT 
                vx_type,
                COUNT(*) as total_tasks,
                countIf(task_status = 'DONE') as done_tasks,
                countIf(task_status = 'TODO') as todo_tasks,
                countIf(task_status = 'DOING') as doing_tasks
            FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
            WHERE plant = 'WJ2' 
              AND factory = 'NBU' 
              AND line = 'E5'
              AND task_create_date = '{date}'
              AND is_excluded = 0
            GROUP BY vx_type
            ORDER BY vx_type
            """
            
            result = client.query(silver_sql)
            
            if result.result_rows:
                print(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
                print("-" * 35)
                for row in result.result_rows:
                    vx_type, total, done, todo, doing = row
                    print(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
            else:
                print(f"❌ {date} 無 ClickHouse 資料")
        
    except Exception as e:
        print(f"❌ ClickHouse 連接失敗: {e}")

def analyze_discrepancy():
    """分析差異"""
    print(f"\n{'='*80}")
    print("差異分析")
    print(f"{'='*80}")
    
    print("\n期望結果顯示:")
    print("- 2025-12-30: V1=3筆, V3=4筆 (總計7筆)")
    print("- 2025-12-31: V1=12筆+1筆, V3=0筆 (總計13筆)")
    
    print("\n實際 MSSQL 結果:")
    print("- 2025-12-30: V1=0筆, V3=7筆 (總計7筆)")
    print("- 2025-12-31: V1=0筆, V3=12筆 (總計12筆)")
    
    print("\n可能的原因:")
    print("1. 期望結果可能基於不同的資料來源或時間點")
    print("2. 期望結果可能包含了其他條件 (如不同的 bypass 設定)")
    print("3. 期望結果可能使用了不同的 V1 歸屬邏輯")
    print("4. 期望結果可能包含了其他 plant/factory/line 的資料")
    
    print("\n建議檢查:")
    print("1. 確認期望結果的資料來源")
    print("2. 檢查是否有其他篩選條件")
    print("3. 確認時間範圍是否一致")
    print("4. 檢查是否有其他 V1 歸屬規則")

def main():
    """主要執行流程"""
    print("檢查期望結果與實際結果的差異")
    
    # 1. 顯示期望結果
    check_expected_results()
    
    # 2. 檢查 MSSQL 詳細條件
    check_mssql_detailed_conditions()
    
    # 3. 檢查 ClickHouse 目前邏輯
    check_clickhouse_current_logic()
    
    # 4. 分析差異
    analyze_discrepancy()

if __name__ == "__main__":
    main()