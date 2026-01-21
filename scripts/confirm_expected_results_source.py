#!/usr/bin/env python3
"""
確認期望結果的來源
基於發現的 bypass 條件差異，重新計算期望結果
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

def calculate_expected_results():
    """計算期望結果的可能來源"""
    print("=" * 80)
    print("計算期望結果的可能來源")
    print("=" * 80)
    
    expected_data = {
        "2025-12-28": {"V1": (0, 0, 0, 0), "V3": (11, 8, 3, 0)},
        "2025-12-30": {"V1": (3, 0, 3, 0), "V3": (4, 0, 4, 0)},
        "2025-12-31": {"V1": (12, 1, 9, 2), "V3": (0, 0, 0, 0)},  # 忽略重複行
    }
    
    print("期望結果:")
    print(f"{'Date':<12} {'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
    print("-" * 50)
    
    for date, vx_data in expected_data.items():
        for vx_type, (total, done, todo, doing) in vx_data.items():
            print(f"{date:<12} {vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
    
    return expected_data

def test_different_scenarios():
    """測試不同的場景組合"""
    print(f"\n{'='*80}")
    print("測試不同場景組合")
    print(f"{'='*80}")
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        scenarios = [
            {
                "name": "場景1: 排除 bypass (目前邏輯)",
                "bypass_condition": "AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)",
                "vx_logic": "TaskDefinitionKey 優先"
            },
            {
                "name": "場景2: 包含 bypass + 工單號優先",
                "bypass_condition": "",
                "vx_logic": "工單號優先"
            },
            {
                "name": "場景3: 只包含 bypass=N + 工單號優先",
                "bypass_condition": "AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)",
                "vx_logic": "工單號優先"
            },
            {
                "name": "場景4: 特定 bypass 組合",
                "bypass_condition": "AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0 OR (var_bypass.LONG_ = 1 AND hti.END_TIME_ IS NOT NULL))",
                "vx_logic": "工單號優先"
            }
        ]
        
        dates = ['2025-12-30', '2025-12-31']
        
        for scenario in scenarios:
            print(f"\n{'-'*60}")
            print(f"{scenario['name']}")
            print(f"{'-'*60}")
            
            for date in dates:
                # 根據場景選擇 VX 歸屬邏輯
                if scenario['vx_logic'] == "工單號優先":
                    vx_case = """
                    CASE 
                        WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                          OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                          OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                        ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                    END"""
                else:  # TaskDefinitionKey 優先
                    vx_case = """
                    CASE 
                        WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                        WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                        WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                        WHEN var_moNumber.TEXT_ LIKE '196%' OR var_moNumber.TEXT_ LIKE '199%' OR var_moNumber.TEXT_ LIKE '200%' 
                          OR var_moNumber.TEXT_ LIKE '210%' OR var_moNumber.TEXT_ LIKE '212%' OR var_moNumber.TEXT_ LIKE '213%' 
                          OR var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
                        ELSE LEFT(hti.TASK_DEF_KEY_, 2)
                    END"""
                
                scenario_sql = f"""
                SELECT 
                    {vx_case} as vx_type,
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
                  {scenario['bypass_condition']}
                GROUP BY {vx_case}
                ORDER BY vx_type
                """
                
                cursor.execute(scenario_sql)
                results = cursor.fetchall()
                
                print(f"\n{date} 結果:")
                print(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
                print("-" * 35)
                
                if results:
                    for row in results:
                        vx_type, total, done, todo, doing = row
                        print(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
                else:
                    print("無資料")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ MSSQL 連接失敗: {e}")

def find_matching_scenario():
    """找出最匹配期望結果的場景"""
    print(f"\n{'='*80}")
    print("找出最匹配期望結果的場景")
    print(f"{'='*80}")
    
    expected_data = {
        "2025-12-30": {"V1": 3, "V3": 4},
        "2025-12-31": {"V1": 12, "V3": 0},
    }
    
    print("期望結果總結:")
    for date, vx_data in expected_data.items():
        print(f"{date}: V1={vx_data['V1']}筆, V3={vx_data.get('V3', 0)}筆")
    
    print("\n實際測試結果分析:")
    print("場景2 (包含 bypass + 工單號優先):")
    print("- 2025-12-30: V1=7筆 (不匹配，期望3筆)")
    print("- 2025-12-31: V1=44筆 (不匹配，期望12筆)")
    
    print("\n可能的解釋:")
    print("1. 期望結果可能來自部分任務的子集")
    print("2. 期望結果可能使用了不同的時間範圍或篩選條件")
    print("3. 期望結果可能來自不同的資料來源")
    print("4. 期望結果可能包含了手動調整或業務規則")

def main():
    """主要執行流程"""
    print("確認期望結果的來源")
    
    # 1. 顯示期望結果
    calculate_expected_results()
    
    # 2. 測試不同場景
    test_different_scenarios()
    
    # 3. 分析匹配情況
    find_matching_scenario()

if __name__ == "__main__":
    main()