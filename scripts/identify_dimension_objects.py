#!/usr/bin/env python3
"""
識別所有需要更新維度補齊邏輯的對象
包括 Silver 層的 View/MVIEW/ETL SQL 和 Gold 層的 Snapshot/Aggregation/Cube
"""

import clickhouse_connect
import pandas as pd
import os
import glob

def main():
    print("🔍 識別需要更新維度補齊邏輯的對象")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 檢查 Silver 層所有產出五階維度的對象
        print("📊 步驟 1: Silver 層 - 產出五階維度的對象")
        print("-" * 50)
        
        silver_objects = []
        
        # 檢查所有 Silver 層的表和 mview
        silver_query = """
        SELECT 
            name,
            engine,
            total_rows
        FROM system.tables
        WHERE database = 'silver'
          AND engine IN ('MaterializedView', 'ReplacingMergeTree', 'MergeTree')
        ORDER BY name
        """
        
        silver_result = client.query(silver_query)
        
        for name, engine, rows in silver_result.result_rows:
            try:
                # 檢查是否有五階維度欄位
                desc_query = f"DESCRIBE silver.{name}"
                desc_result = client.query(desc_query)
                columns = [row[0] for row in desc_result.result_rows]
                
                # 檢查是否包含五階維度
                dimension_cols = []
                for col in columns:
                    if col.lower() in ['region', 'region_code', 'plant', 'plant_code', 'factory', 'factory_code', 'line_name', 'line_code']:
                        dimension_cols.append(col)
                
                if dimension_cols:
                    silver_objects.append({
                        'name': f'silver.{name}',
                        'engine': engine,
                        'rows': rows,
                        'dimension_cols': dimension_cols
                    })
                    
                    print(f"✅ {name} ({engine}): {rows:,} rows")
                    print(f"   維度欄位: {', '.join(dimension_cols)}")
                    
            except Exception as e:
                print(f"❌ 檢查 {name} 失敗: {str(e)}")
        
        print(f"\n📋 Silver 層找到 {len(silver_objects)} 個包含五階維度的對象")
        
        # 2. 檢查 Gold 層所有從 Silver 拉五階維度的對象
        print(f"\n📊 步驟 2: Gold 層 - 從 Silver 拉五階維度的對象")
        print("-" * 50)
        
        gold_objects = []
        
        # 檢查所有 Gold 層的表和 mview
        gold_query = """
        SELECT 
            name,
            engine,
            total_rows
        FROM system.tables
        WHERE database = 'gold'
          AND engine IN ('MaterializedView', 'ReplacingMergeTree', 'MergeTree')
        ORDER BY name
        """
        
        gold_result = client.query(gold_query)
        
        for name, engine, rows in gold_result.result_rows:
            try:
                # 檢查是否有五階維度欄位
                desc_query = f"DESCRIBE gold.{name}"
                desc_result = client.query(desc_query)
                columns = [row[0] for row in desc_result.result_rows]
                
                # 檢查是否包含五階維度
                dimension_cols = []
                for col in columns:
                    if col.lower() in ['region', 'region_code', 'plant', 'plant_code', 'factory', 'factory_code', 'line_name', 'line_code']:
                        dimension_cols.append(col)
                
                if dimension_cols:
                    gold_objects.append({
                        'name': f'gold.{name}',
                        'engine': engine,
                        'rows': rows,
                        'dimension_cols': dimension_cols
                    })
                    
                    print(f"✅ {name} ({engine}): {rows:,} rows")
                    print(f"   維度欄位: {', '.join(dimension_cols)}")
                    
            except Exception as e:
                print(f"❌ 檢查 {name} 失敗: {str(e)}")
        
        print(f"\n📋 Gold 層找到 {len(gold_objects)} 個包含五階維度的對象")
        
        # 3. 檢查 SQL 檔案
        print(f"\n📊 步驟 3: 檢查相關 SQL 檔案")
        print("-" * 50)
        
        sql_files = []
        
        # 搜尋所有 SQL 檔案
        for pattern in ['sql/*.sql', 'sql/**/*.sql']:
            for file_path in glob.glob(pattern, recursive=True):
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read().lower()
                            
                        # 檢查是否包含五階維度相關內容
                        dimension_keywords = ['region', 'plant', 'factory', 'line_name', 'mfg_five_level', 'varinst', 'mdm']
                        
                        if any(keyword in content for keyword in dimension_keywords):
                            sql_files.append(file_path)
                            print(f"✅ {file_path}")
                            
                    except Exception as e:
                        print(f"❌ 讀取 {file_path} 失敗: {str(e)}")
        
        print(f"\n📋 找到 {len(sql_files)} 個相關 SQL 檔案")
        
        # 4. 檢查 Cube.js 檔案
        print(f"\n📊 步驟 4: 檢查 Cube.js 檔案")
        print("-" * 50)
        
        cube_files = []
        
        # 搜尋所有 Cube.js 檔案
        for pattern in ['cube/**/*.js', 'cube/model/**/*.js']:
            for file_path in glob.glob(pattern, recursive=True):
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read().lower()
                            
                        # 檢查是否包含五階維度相關內容
                        if any(keyword in content for keyword in ['region', 'plant', 'factory', 'line']):
                            cube_files.append(file_path)
                            print(f"✅ {file_path}")
                            
                    except Exception as e:
                        print(f"❌ 讀取 {file_path} 失敗: {str(e)}")
        
        print(f"\n📋 找到 {len(cube_files)} 個相關 Cube.js 檔案")
        
        # 5. 總結需要更新的對象
        print(f"\n📊 步驟 5: 總結需要更新的對象")
        print("-" * 50)
        
        print("🔄 需要更新的對象清單:")
        print("\n🥈 Silver 層 (實作 VARINST 優先，MDM 補齊):")
        for obj in silver_objects:
            print(f"   - {obj['name']} ({obj['engine']})")
        
        print("\n🥇 Gold 層 (信任 Silver 已補齊的欄位):")
        for obj in gold_objects:
            print(f"   - {obj['name']} ({obj['engine']})")
        
        print(f"\n📄 SQL 檔案:")
        for file_path in sql_files[:10]:  # 只顯示前10個
            print(f"   - {file_path}")
        if len(sql_files) > 10:
            print(f"   ... 還有 {len(sql_files) - 10} 個檔案")
        
        print(f"\n🧊 Cube.js 檔案:")
        for file_path in cube_files:
            print(f"   - {file_path}")
        
        return {
            'silver_objects': silver_objects,
            'gold_objects': gold_objects,
            'sql_files': sql_files,
            'cube_files': cube_files
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
        print(f"\n✅ 識別完成")
        print(f"   Silver 對象: {len(result['silver_objects'])}")
        print(f"   Gold 對象: {len(result['gold_objects'])}")
        print(f"   SQL 檔案: {len(result['sql_files'])}")
        print(f"   Cube 檔案: {len(result['cube_files'])}")
    else:
        print(f"\n❌ 識別失敗")