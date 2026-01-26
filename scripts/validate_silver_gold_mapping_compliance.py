#!/usr/bin/env python3
"""
驗證 Silver/Gold 層五階維度映射合規性
"""

import clickhouse_connect
import pandas as pd
import json

def main():
    print("🔍 驗證 Silver/Gold 層五階維度映射合規性")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 找出所有可能的五階維度物件
        print("📊 步驟 1：找出五階維度相關物件")
        
        # 檢查 Silver 層
        silver_objects = []
        silver_query = """
        SELECT name, engine
        FROM system.tables 
        WHERE database = 'silver'
        ORDER BY name
        """
        
        silver_result = client.query(silver_query)
        if silver_result.result_rows:
            for row in silver_result.result_rows:
                table_name = row[0]
                engine = row[1]
                
                # 檢查是否有五階維度欄位
                columns_query = f"""
                SELECT name
                FROM system.columns 
                WHERE database = 'silver' AND table = '{table_name}'
                  AND name IN ('region', 'plant', 'factory', 'lineName', 'line_name', 'line')
                """
                
                columns_result = client.query(columns_query)
                if columns_result.result_rows and len(columns_result.result_rows) >= 3:
                    dimension_columns = [col[0] for col in columns_result.result_rows]
                    silver_objects.append((table_name, engine, dimension_columns))
        
        # 檢查 Gold 層
        gold_objects = []
        gold_query = """
        SELECT name, engine
        FROM system.tables 
        WHERE database = 'gold'
        ORDER BY name
        """
        
        gold_result = client.query(gold_query)
        if gold_result.result_rows:
            for row in gold_result.result_rows:
                table_name = row[0]
                engine = row[1]
                
                # 檢查是否有五階維度欄位
                columns_query = f"""
                SELECT name
                FROM system.columns 
                WHERE database = 'gold' AND table = '{table_name}'
                  AND name IN ('region', 'plant', 'factory', 'lineName', 'line_name', 'line')
                """
                
                columns_result = client.query(columns_query)
                if columns_result.result_rows and len(columns_result.result_rows) >= 3:
                    dimension_columns = [col[0] for col in columns_result.result_rows]
                    gold_objects.append((table_name, engine, dimension_columns))
        
        print(f"✅ Silver 層找到 {len(silver_objects)} 個五階維度物件")
        for table_name, engine, columns in silver_objects:
            print(f"   silver.{table_name} ({engine}): {columns}")
        
        print(f"✅ Gold 層找到 {len(gold_objects)} 個五階維度物件")
        for table_name, engine, columns in gold_objects:
            print(f"   gold.{table_name} ({engine}): {columns}")
        
        # 2. 對每個物件進行詳細分析
        print("\n📊 步驟 2：分析物件 DDL 和映射邏輯")
        
        all_objects = [('silver', obj) for obj in silver_objects] + [('gold', obj) for obj in gold_objects]
        analysis_results = []
        
        for db, (table_name, engine, columns) in all_objects:
            print(f"\n🔍 分析 {db}.{table_name}")
            
            # 取得 DDL
            try:
                ddl_query = f"SHOW CREATE TABLE {db}.{table_name}"
                ddl_result = client.query(ddl_query)
                ddl = ddl_result.result_rows[0][0] if ddl_result.result_rows else ""
                
                # 分析 DDL 內容
                analysis = {
                    'database': db,
                    'table_name': table_name,
                    'engine': engine,
                    'dimension_columns': columns,
                    'ddl_length': len(ddl),
                    'has_mdm_logic': 'mdm' in ddl.lower(),
                    'has_varinst_logic': 'varinst' in ddl.lower(),
                    'has_fallback_logic': 'coalesce' in ddl.lower() or 'ifnull' in ddl.lower(),
                    'has_join_logic': 'join' in ddl.lower(),
                    'ddl_snippet': ddl[:500] + '...' if len(ddl) > 500 else ddl
                }
                
                analysis_results.append(analysis)
                
                print(f"   DDL 長度: {analysis['ddl_length']} 字元")
                print(f"   包含 MDM 邏輯: {'✅' if analysis['has_mdm_logic'] else '❌'}")
                print(f"   包含 VARINST 邏輯: {'✅' if analysis['has_varinst_logic'] else '❌'}")
                print(f"   包含 Fallback 邏輯: {'✅' if analysis['has_fallback_logic'] else '❌'}")
                print(f"   包含 Join 邏輯: {'✅' if analysis['has_join_logic'] else '❌'}")
                
            except Exception as e:
                print(f"   ❌ 無法取得 DDL: {str(e)}")
                analysis_results.append({
                    'database': db,
                    'table_name': table_name,
                    'engine': engine,
                    'dimension_columns': columns,
                    'error': str(e)
                })
        
        # 3. 重點物件深度分析
        print("\n📊 步驟 3：重點物件深度分析")
        
        # 找出最可能包含完整五階維度邏輯的物件
        priority_objects = []
        for analysis in analysis_results:
            if (analysis.get('has_mdm_logic', False) and 
                analysis.get('has_varinst_logic', False) and
                len(analysis.get('dimension_columns', [])) >= 4):
                priority_objects.append(analysis)
        
        print(f"✅ 找到 {len(priority_objects)} 個重點物件進行深度分析")
        
        for analysis in priority_objects:
            db = analysis['database']
            table_name = analysis['table_name']
            print(f"\n🎯 深度分析: {db}.{table_name}")
            
            # 抽樣檢查資料
            sample_query = f"""
            SELECT 
                region, plant, factory, 
                CASE WHEN hasColumn('{db}', '{table_name}', 'lineName') THEN lineName
                     WHEN hasColumn('{db}', '{table_name}', 'line_name') THEN line_name
                     WHEN hasColumn('{db}', '{table_name}', 'line') THEN line
                     ELSE '' END as line_value,
                count() as record_count
            FROM {db}.{table_name}
            WHERE region != '' AND plant != '' AND factory != ''
            GROUP BY region, plant, factory, line_value
            ORDER BY record_count DESC
            LIMIT 10
            """
            
            try:
                sample_result = client.query(sample_query)
                if sample_result.result_rows:
                    print("   📊 資料抽樣:")
                    df_sample = pd.DataFrame(sample_result.result_rows, columns=sample_result.column_names)
                    for _, row in df_sample.iterrows():
                        print(f"      {row['region']}-{row['plant']}-{row['factory']}-{row['line_value']} ({row['record_count']} 筆)")
                else:
                    print("   ❌ 無資料或查詢失敗")
            except Exception as e:
                print(f"   ❌ 抽樣查詢失敗: {str(e)}")
        
        # 4. 輸出分析結果
        print("\n" + "=" * 80)
        print("📋 分析結果摘要")
        
        total_objects = len(analysis_results)
        mdm_objects = len([a for a in analysis_results if a.get('has_mdm_logic', False)])
        varinst_objects = len([a for a in analysis_results if a.get('has_varinst_logic', False)])
        fallback_objects = len([a for a in analysis_results if a.get('has_fallback_logic', False)])
        
        print(f"總物件數: {total_objects}")
        print(f"包含 MDM 邏輯: {mdm_objects} ({mdm_objects/total_objects*100:.1f}%)")
        print(f"包含 VARINST 邏輯: {varinst_objects} ({varinst_objects/total_objects*100:.1f}%)")
        print(f"包含 Fallback 邏輯: {fallback_objects} ({fallback_objects/total_objects*100:.1f}%)")
        print(f"重點分析物件: {len(priority_objects)}")
        
        return {
            'analysis_results': analysis_results,
            'priority_objects': priority_objects,
            'summary': {
                'total_objects': total_objects,
                'mdm_objects': mdm_objects,
                'varinst_objects': varinst_objects,
                'fallback_objects': fallback_objects
            }
        }
        
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        client.close()

if __name__ == "__main__":
    result = main()
    if result:
        print(f"\n✅ 分析完成，找到 {len(result['priority_objects'])} 個重點物件")
    else:
        print("\n❌ 分析失敗")