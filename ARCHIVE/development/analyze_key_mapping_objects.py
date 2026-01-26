#!/usr/bin/env python3
"""
深度分析關鍵的五階維度映射物件
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 深度分析關鍵五階維度映射物件")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 重點分析物件列表
        key_objects = [
            'silver.mv_fact_task_vx_attribution_mdm',
            'silver.mv_fact_task_vx_attribution',
            'gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV'
        ]
        
        for obj in key_objects:
            print(f"\n🎯 分析物件: {obj}")
            print("-" * 60)
            
            # 1. 取得 DDL
            try:
                ddl_query = f"SHOW CREATE TABLE {obj}"
                ddl_result = client.query(ddl_query)
                ddl = ddl_result.result_rows[0][0] if ddl_result.result_rows else ""
                
                print(f"📋 DDL 分析:")
                print(f"   長度: {len(ddl)} 字元")
                print(f"   包含 MDM: {'✅' if 'mdm' in ddl.lower() else '❌'}")
                print(f"   包含 VARINST: {'✅' if 'varinst' in ddl.lower() else '❌'}")
                print(f"   包含 COALESCE: {'✅' if 'coalesce' in ddl.lower() else '❌'}")
                
                # 顯示關鍵部分的 DDL
                lines = ddl.split('\n')
                dimension_lines = []
                for i, line in enumerate(lines):
                    if any(dim in line.lower() for dim in ['region', 'plant', 'factory', 'line']):
                        dimension_lines.append(f"   {i+1:3d}: {line.strip()}")
                
                if dimension_lines:
                    print(f"📊 維度相關 DDL 片段:")
                    for line in dimension_lines[:10]:  # 只顯示前10行
                        print(line)
                    if len(dimension_lines) > 10:
                        print(f"   ... (還有 {len(dimension_lines)-10} 行)")
                
            except Exception as e:
                print(f"   ❌ 無法取得 DDL: {str(e)}")
                continue
            
            # 2. 檢查欄位結構
            try:
                columns_query = f"""
                SELECT name, type
                FROM system.columns 
                WHERE database = '{obj.split('.')[0]}' AND table = '{obj.split('.')[1]}'
                  AND (name IN ('region', 'plant', 'factory', 'lineName', 'line_name', 'line')
                       OR name LIKE '%region%' OR name LIKE '%plant%' OR name LIKE '%factory%' OR name LIKE '%line%')
                ORDER BY name
                """
                
                columns_result = client.query(columns_query)
                if columns_result.result_rows:
                    print(f"📊 維度欄位:")
                    df_columns = pd.DataFrame(columns_result.result_rows, columns=columns_result.column_names)
                    for _, row in df_columns.iterrows():
                        print(f"   {row['name']}: {row['type']}")
                
            except Exception as e:
                print(f"   ❌ 無法取得欄位資訊: {str(e)}")
            
            # 3. 抽樣資料檢查
            try:
                # 先檢查實際欄位名稱
                actual_columns_query = f"""
                SELECT name
                FROM system.columns 
                WHERE database = '{obj.split('.')[0]}' AND table = '{obj.split('.')[1]}'
                  AND name IN ('region', 'plant', 'factory', 'lineName', 'line_name', 'line')
                """
                
                actual_columns_result = client.query(actual_columns_query)
                actual_columns = [row[0] for row in actual_columns_result.result_rows] if actual_columns_result.result_rows else []
                
                if len(actual_columns) >= 3:
                    # 構建動態查詢
                    select_fields = []
                    for col in ['region', 'plant', 'factory']:
                        if col in actual_columns:
                            select_fields.append(col)
                        else:
                            select_fields.append("'' as " + col)
                    
                    # 處理 line 欄位的多種可能名稱
                    if 'lineName' in actual_columns:
                        select_fields.append('lineName as line_value')
                    elif 'line_name' in actual_columns:
                        select_fields.append('line_name as line_value')
                    elif 'line' in actual_columns:
                        select_fields.append('line as line_value')
                    else:
                        select_fields.append("'' as line_value")
                    
                    sample_query = f"""
                    SELECT 
                        {', '.join(select_fields)},
                        count() as record_count
                    FROM {obj}
                    WHERE 1=1
                    GROUP BY {', '.join([f.split(' as ')[0] if ' as ' in f else f for f in select_fields[:-1]])}
                    ORDER BY record_count DESC
                    LIMIT 10
                    """
                    
                    sample_result = client.query(sample_query)
                    if sample_result.result_rows:
                        print(f"📊 資料抽樣 (前10組合):")
                        df_sample = pd.DataFrame(sample_result.result_rows, columns=sample_result.column_names)
                        for _, row in df_sample.iterrows():
                            print(f"   {row.get('region', '')}-{row.get('plant', '')}-{row.get('factory', '')}-{row.get('line_value', '')} ({row['record_count']} 筆)")
                    else:
                        print("   ❌ 無資料")
                else:
                    print("   ❌ 維度欄位不足，跳過資料抽樣")
                
            except Exception as e:
                print(f"   ❌ 資料抽樣失敗: {str(e)}")
        
        # 4. 比較分析
        print(f"\n" + "=" * 80)
        print("🔍 關鍵發現和建議")
        
        # 檢查 silver.mv_fact_task_vx_attribution_mdm 的具體實作
        print(f"\n📋 重點物件 silver.mv_fact_task_vx_attribution_mdm 詳細分析:")
        
        try:
            ddl_query = "SHOW CREATE TABLE silver.mv_fact_task_vx_attribution_mdm"
            ddl_result = client.query(ddl_query)
            ddl = ddl_result.result_rows[0][0] if ddl_result.result_rows else ""
            
            # 分析維度交換邏輯
            print("🔍 檢查維度交換邏輯:")
            if 'coalesce' in ddl.lower():
                print("   ✅ 發現 COALESCE 邏輯")
                
                # 尋找 COALESCE 相關的行
                lines = ddl.split('\n')
                coalesce_lines = []
                for i, line in enumerate(lines):
                    if 'coalesce' in line.lower() and any(dim in line.lower() for dim in ['plant', 'factory', 'region', 'line']):
                        coalesce_lines.append(f"   {i+1:3d}: {line.strip()}")
                
                if coalesce_lines:
                    print("   COALESCE 維度邏輯:")
                    for line in coalesce_lines:
                        print(line)
            
            # 檢查 MDM join 邏輯
            print("\n🔍 檢查 MDM JOIN 邏輯:")
            if 'join' in ddl.lower() and 'mdm' in ddl.lower():
                print("   ✅ 發現 MDM JOIN")
                
                join_lines = []
                lines = ddl.split('\n')
                for i, line in enumerate(lines):
                    if 'join' in line.lower() and 'mdm' in line.lower():
                        join_lines.append(f"   {i+1:3d}: {line.strip()}")
                
                if join_lines:
                    print("   MDM JOIN 邏輯:")
                    for line in join_lines[:5]:  # 只顯示前5行
                        print(line)
            
            # 檢查維度交換
            print("\n🔍 檢查維度交換實作:")
            plant_factory_swap = False
            if 'varinst_plant' in ddl.lower() and 'mdm' in ddl.lower():
                if 'factory' in ddl.lower():
                    print("   ⚠️  可能存在 plant/factory 維度交換邏輯")
                    plant_factory_swap = True
            
            if not plant_factory_swap:
                print("   ❌ 未發現明確的 plant/factory 維度交換邏輯")
            
        except Exception as e:
            print(f"   ❌ 詳細分析失敗: {str(e)}")
        
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
        print(f"\n✅ 深度分析完成")
    else:
        print("\n❌ 分析失敗")