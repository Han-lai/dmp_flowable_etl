#!/usr/bin/env python3
"""
分析 V1/V3 條件邏輯錯誤
找出為什麼 2025-12-30 期望 V1=3,V3=4 但實際 V1=7,V3=0
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

def analyze_task_distribution():
    """分析任務分布，找出可能的邏輯錯誤"""
    print("=" * 80)
    print("分析 2025-12-30 任務分布")
    print("=" * 80)
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 詳細分析每個任務的條件
        detail_sql = """
        SELECT 
            hti.ID_ as task_id,
            hti.TASK_DEF_KEY_ as task_definition_key,
            var_moNumber.TEXT_ as mo_number,
            CASE
                WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                ELSE 'TODO'
            END AS task_status,
            
            -- 分析各種條件
            CASE WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 1 ELSE 0 END as has_v1_defkey,
            CASE WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 1 ELSE 0 END as has_v2_defkey,
            CASE WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 1 ELSE 0 END as has_v3_defkey,
            
            -- 工單號條件
            CASE WHEN var_moNumber.TEXT_ LIKE '196%' THEN 1 ELSE 0 END as mo_196,
            CASE WHEN var_moNumber.TEXT_ LIKE '199%' THEN 1 ELSE 0 END as mo_199,
            CASE WHEN var_moNumber.TEXT_ LIKE '200%' THEN 1 ELSE 0 END as mo_200,
            CASE WHEN var_moNumber.TEXT_ LIKE '210%' THEN 1 ELSE 0 END as mo_210,
            CASE WHEN var_moNumber.TEXT_ LIKE '212%' THEN 1 ELSE 0 END as mo_212,
            CASE WHEN var_moNumber.TEXT_ LIKE '213%' THEN 1 ELSE 0 END as mo_213,
            CASE WHEN var_moNumber.TEXT_ LIKE '315%' THEN 1 ELSE 0 END as mo_315,
            
            -- 不同的 VX 歸屬邏輯
            -- 邏輯1: 工單號優先
            CASE 
                WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                  OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                  OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                ELSE LEFT(hti.TASK_DEF_KEY_, 2)
            END as vx_mo_first,
            
            -- 邏輯2: TaskDefinitionKey 優先 (目前邏輯)
            CASE 
                WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                  OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                  OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                ELSE LEFT(hti.TASK_DEF_KEY_, 2)
            END as vx_defkey_first,
            
            -- 邏輯3: 可能的混合邏輯 (某些條件下工單號優先)
            CASE 
                WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                -- 特殊條件：V3_5_1_0_1 + 315% 工單號 → V1
                WHEN hti.TASK_DEF_KEY_ = 'V3_5_1_0_1' AND var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                -- 特殊條件：V3_5_1_0_1 + 199% 工單號 → 保持 V3
                WHEN hti.TASK_DEF_KEY_ = 'V3_5_1_0_1' AND var_moNumber.TEXT_ LIKE '199%' THEN 'V3'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                  OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                  OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                ELSE LEFT(hti.TASK_DEF_KEY_, 2)
            END as vx_mixed_logic
            
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
          AND CONVERT(DATE, hti.START_TIME_) = '2025-12-30'
          AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
        ORDER BY hti.TASK_DEF_KEY_, var_moNumber.TEXT_
        """
        
        cursor.execute(detail_sql)
        results = cursor.fetchall()
        
        if results:
            print(f"\n2025-12-30 任務詳細分析:")
            print(f"{'TaskId':<15} {'DefKey':<15} {'MoNumber':<12} {'Status':<8} {'Mo_First':<9} {'DefKey_First':<12} {'Mixed':<8}")
            print("-" * 100)
            
            logic_stats = {
                'mo_first': {'V1': 0, 'V2': 0, 'V3': 0},
                'defkey_first': {'V1': 0, 'V2': 0, 'V3': 0},
                'mixed_logic': {'V1': 0, 'V2': 0, 'V3': 0}
            }
            
            for row in results:
                task_id, def_key, mo_number, status, has_v1, has_v2, has_v3, \
                mo_196, mo_199, mo_200, mo_210, mo_212, mo_213, mo_315, \
                vx_mo_first, vx_defkey_first, vx_mixed = row
                
                print(f"{task_id[:15]:<15} {def_key:<15} {mo_number or 'NULL':<12} {status:<8} {vx_mo_first:<9} {vx_defkey_first:<12} {vx_mixed:<8}")
                
                # 統計各種邏輯的結果
                logic_stats['mo_first'][vx_mo_first] += 1
                logic_stats['defkey_first'][vx_defkey_first] += 1
                logic_stats['mixed_logic'][vx_mixed] += 1
            
            print(f"\n統計結果:")
            print(f"{'邏輯':<20} {'V1':<4} {'V2':<4} {'V3':<4} {'總計':<6}")
            print("-" * 40)
            
            for logic_name, stats in logic_stats.items():
                total = sum(stats.values())
                print(f"{logic_name:<20} {stats['V1']:<4} {stats['V2']:<4} {stats['V3']:<4} {total:<6}")
            
            print(f"\n期望結果: V1=3, V3=4")
            print(f"哪個邏輯最接近期望結果？")
            
            # 檢查哪個邏輯最接近期望結果
            expected_v1, expected_v3 = 3, 4
            
            for logic_name, stats in logic_stats.items():
                v1_count = stats['V1']
                v3_count = stats['V3']
                v1_diff = abs(v1_count - expected_v1)
                v3_diff = abs(v3_count - expected_v3)
                total_diff = v1_diff + v3_diff
                
                print(f"{logic_name}: V1差異={v1_diff}, V3差異={v3_diff}, 總差異={total_diff}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ MSSQL 連接失敗: {e}")

def test_custom_logic_scenarios():
    """測試自定義邏輯場景"""
    print(f"\n{'='*80}")
    print("測試自定義邏輯場景")
    print(f"{'='*80}")
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 測試各種可能的邏輯組合
        scenarios = [
            {
                "name": "場景A: 315%工單→V1, 199%工單→V3",
                "logic": """
                CASE 
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                    WHEN var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                    WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                      OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' THEN 'V1'
                    ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                END"""
            },
            {
                "name": "場景B: 只有特定315%工單→V1",
                "logic": """
                CASE 
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                    WHEN var_moNumber.TEXT_ IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                    WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                      OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' THEN 'V1'
                    ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                END"""
            },
            {
                "name": "場景C: 按任務狀態分類",
                "logic": """
                CASE 
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                    WHEN (var_moNumber.TEXT_ LIKE '315%' AND hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NULL) THEN 'V1'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                    WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                      OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' THEN 'V1'
                    ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                END"""
            }
        ]
        
        for scenario in scenarios:
            print(f"\n{'-'*60}")
            print(f"{scenario['name']}")
            print(f"{'-'*60}")
            
            scenario_sql = f"""
            SELECT 
                {scenario['logic']} as vx_type,
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
              AND CONVERT(DATE, hti.START_TIME_) = '2025-12-30'
              AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
            GROUP BY {scenario['logic']}
            ORDER BY vx_type
            """
            
            cursor.execute(scenario_sql)
            results = cursor.fetchall()
            
            print(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
            print("-" * 35)
            
            if results:
                for row in results:
                    vx_type, total, done, todo, doing = row
                    print(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
                
                # 檢查是否匹配期望結果
                v1_count = next((row[1] for row in results if row[0] == 'V1'), 0)
                v3_count = next((row[1] for row in results if row[0] == 'V3'), 0)
                
                if v1_count == 3 and v3_count == 4:
                    print(f"🎯 **完全匹配期望結果！**")
                elif abs(v1_count - 3) + abs(v3_count - 4) <= 2:
                    print(f"⚠️ 接近期望結果 (V1差異={abs(v1_count - 3)}, V3差異={abs(v3_count - 4)})")
            else:
                print("無資料")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ MSSQL 連接失敗: {e}")

def main():
    """主要執行流程"""
    print("分析 V1/V3 條件邏輯錯誤")
    
    # 1. 分析任務分布
    analyze_task_distribution()
    
    # 2. 測試自定義邏輯場景
    test_custom_logic_scenarios()
    
    print(f"\n{'='*80}")
    print("結論與建議")
    print(f"{'='*80}")
    print("基於分析結果，找出最接近期望結果 V1=3,V3=4 的邏輯")
    print("如果找到匹配的邏輯，建議調整 V1/V3 歸屬規則")

if __name__ == "__main__":
    main()