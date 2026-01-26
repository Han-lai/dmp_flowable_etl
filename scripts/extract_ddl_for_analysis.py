#!/usr/bin/env python3
"""
提取關鍵物件的完整 DDL 進行分析
"""

import clickhouse_connect

def main():
    print("🔍 提取關鍵物件 DDL 進行分析")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 提取 silver.mv_fact_task_vx_attribution_mdm 的完整 DDL
        ddl_query = "SHOW CREATE TABLE silver.mv_fact_task_vx_attribution_mdm"
        ddl_result = client.query(ddl_query)
        ddl = ddl_result.result_rows[0][0] if ddl_result.result_rows else ""
        
        print("📋 silver.mv_fact_task_vx_attribution_mdm 完整 DDL:")
        print("=" * 80)
        print(ddl)
        print("=" * 80)
        
        # 分析關鍵部分
        print("\n🔍 關鍵邏輯分析:")
        
        lines = ddl.split('\n')
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if ('coalesce' in line_lower and 
                any(dim in line_lower for dim in ['plant', 'factory', 'region', 'line'])):
                print(f"Line {i+1:3d}: {line.strip()}")
        
        # 檢查維度交換邏輯
        print(f"\n🔍 維度交換邏輯檢查:")
        
        # 尋找 flowable_plant 和 flowable_factory 的使用
        flowable_plant_lines = []
        flowable_factory_lines = []
        mdm_plant_lines = []
        mdm_factory_lines = []
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if 'flowable_plant' in line_lower:
                flowable_plant_lines.append((i+1, line.strip()))
            if 'flowable_factory' in line_lower:
                flowable_factory_lines.append((i+1, line.strip()))
            if 'mdm_plant' in line_lower and 'mdm_plant_' not in line_lower:
                mdm_plant_lines.append((i+1, line.strip()))
            if 'mdm_factory' in line_lower and 'mdm_factory_' not in line_lower:
                mdm_factory_lines.append((i+1, line.strip()))
        
        print("📊 Flowable Plant 使用:")
        for line_num, line in flowable_plant_lines:
            print(f"   Line {line_num}: {line}")
        
        print("📊 Flowable Factory 使用:")
        for line_num, line in flowable_factory_lines:
            print(f"   Line {line_num}: {line}")
        
        print("📊 MDM Plant 使用:")
        for line_num, line in mdm_plant_lines:
            print(f"   Line {line_num}: {line}")
        
        print("📊 MDM Factory 使用:")
        for line_num, line in mdm_factory_lines:
            print(f"   Line {line_num}: {line}")
        
        # 分析維度交換模式
        print(f"\n🎯 維度交換模式分析:")
        
        # 檢查是否有 flowable_plant -> factory 的映射
        plant_to_factory = False
        factory_to_plant = False
        
        for line_num, line in flowable_plant_lines:
            if 'factory' in line.lower() and 'coalesce' in line.lower():
                print(f"   ✅ 發現 flowable_plant -> factory 映射: Line {line_num}")
                plant_to_factory = True
        
        for line_num, line in flowable_factory_lines:
            if 'plant' in line.lower() and 'coalesce' in line.lower():
                print(f"   ✅ 發現 flowable_factory -> plant 映射: Line {line_num}")
                factory_to_plant = True
        
        if plant_to_factory and factory_to_plant:
            print("   🔄 確認存在維度交換邏輯")
        else:
            print("   ❌ 未確認維度交換邏輯")
        
        return True
        
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        client.close()

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n✅ DDL 分析完成")
    else:
        print("\n❌ 分析失敗")