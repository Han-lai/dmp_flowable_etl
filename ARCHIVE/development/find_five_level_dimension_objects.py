#!/usr/bin/env python3
"""
找出所有會產出五階維度的 Silver/Gold 層物件
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 找出所有五階維度相關物件")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 找出所有 Silver 層物件
        print("📊 步驟 1：Silver 層物件")
        silver_query = """
        SELECT 
            database,
            name,
            engine,
            create_table_query
        FROM system.tables 
        WHERE database = 'silver'
          AND (name LIKE '%five%' OR name LIKE '%dimension%' OR name LIKE '%mfg%' 
               OR name LIKE '%task%' OR name LIKE '%bpm%' OR name LIKE '%varinst%')
        ORDER BY name
        """
        
        silver_result = client.query(silver_query)
        if silver_result.result_rows:
            print("✅ Silver 層相關物件：")
            df_silver = pd.DataFrame(silver_result.result_rows, columns=silver_result.column_names)
            for _, row in df_silver.iterrows():
                print(f"   {row['name']} ({row['engine']})")
        
        # 2. 找出所有 Gold 層物件
        print("\n📊 步驟 2：Gold 層物件")
        gold_query = """
        SELECT 
            database,
            name,
            engine,
            create_table_query
        FROM system.tables 
        WHERE database = 'gold'
          AND (name LIKE '%five%' OR name LIKE '%dimension%' OR name LIKE '%mfg%' 
               OR name LIKE '%task%' OR name LIKE '%bpm%' OR name LIKE '%l5%'
               OR name LIKE '%completion%' OR name LIKE '%dashboard%')
        ORDER BY name
        """
        
        gold_result = client.query(gold_query)
        if gold_result.result_rows:
            print("✅ Gold 層相關物件：")
            df_gold = pd.DataFrame(gold_result.result_rows, columns=gold_result.column_names)
            for _, row in df_gold.iterrows():
                print(f"   {row['name']} ({row['engine']})")
        
        # 3. 檢查每個物件是否包含五階維度欄位
        print("\n📊 步驟 3：檢查五階維度欄位")
        
        all_objects = []
        if silver_result.result_rows:
            for row in silver_result.result_rows:
                all_objects.append(('silver', row[1], row[2]))
        
        if gold_result.result_rows:
            for row in gold_result.result_rows:
                all_objects.append(('gold', row[1], row[2]))
        
        five_level_objects = []
        
        for db, table_name, engine in all_objects:
            # 檢查欄位
            columns_query = f"""
            SELECT name, type
            FROM system.columns 
            WHERE database = '{db}' AND table = '{table_name}'
              AND (name IN ('region', 'plant', 'factory', 'lineName', 'line_name', 'line') 
                   OR name LIKE '%region%' OR name LIKE '%plant%' OR name LIKE '%factory%' OR name LIKE '%line%')
            ORDER BY name
            """
            
            columns_result = client.query(columns_query)
            if columns_result.result_rows and len(columns_result.result_rows) >= 3:  # 至少3個維度欄位
                df_columns = pd.DataFrame(columns_result.result_rows, columns=columns_result.column_names)
                dimension_columns = list(df_columns['name'])
                five_level_objects.append((db, table_name, engine, dimension_columns))
                print(f"   ✅ {db}.{table_name}: {dimension_columns}")
        
        # 4. 輸出結果摘要
        print("\n" + "=" * 80)
        print("📋 發現的五階維度物件：")
        
        for db, table_name, engine, columns in five_level_objects:
            print(f"\n🔍 {db}.{table_name} ({engine})")
            print(f"   維度欄位: {', '.join(columns)}")
            
            # 取得 DDL
            ddl_query = f"SHOW CREATE TABLE {db}.{table_name}"
            try:
                ddl_result = client.query(ddl_query)
                if ddl_result.result_rows:
                    ddl = ddl_result.result_rows[0][0]
                    print(f"   DDL 長度: {len(ddl)} 字元")
                    # 檢查是否包含 MDM 相關 join
                    if 'mdm' in ddl.lower():
                        print("   ✅ 包含 MDM 相關邏輯")
                    if 'varinst' in ddl.lower():
                        print("   ✅ 包含 VARINST 相關邏輯")
                    if 'coalesce' in ddl.lower() or 'ifnull' in ddl.lower():
                        print("   ✅ 包含 fallback 邏輯")
            except Exception as e:
                print(f"   ❌ 無法取得 DDL: {str(e)}")
        
        print(f"\n📊 總計找到 {len(five_level_objects)} 個五階維度相關物件")
        
        # 5. 儲存結果供後續使用
        result_data = {
            'objects': five_level_objects,
            'total_count': len(five_level_objects)
        }
        
        return result_data
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        client.close()

if __name__ == "__main__":
    result = main()
    if result:
        print(f"\n✅ 成功找到 {result['total_count']} 個物件")
    else:
        print("\n❌ 執行失敗")