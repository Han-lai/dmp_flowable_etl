#!/usr/bin/env python3
"""
根據正確的製造五階維度映射，查找 CNE WJ2 NBU E5 的資料
正確映射：Region=CNE, Plant=WJ2, Factory=NBU, Line=E5
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 根據正確的製造五階維度映射查找 CNE WJ2 NBU E5")
    print("正確映射：Region=CNE, Plant=WJ2, Factory=NBU, Line=E5")
    print("=" * 80)
    
    # ClickHouse 連線設定
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 先檢查 MDM 維度表是否存在正確的映射
        print("📊 步驟 1：檢查 MDM 維度表")
        mdm_query = """
        SELECT DISTINCT
            region_code,
            region_name,
            plant_code,
            plant_name,
            factory_code,
            factory_name,
            line_code,
            line_name,
            line_desc
        FROM silver.dim_mfg_five_level
        WHERE region_code = 'CNE'
          AND plant_code = 'WJ2'
          AND factory_code = 'NBU'
          AND (line_code = 'E5' OR line_name = 'E5' OR line_name LIKE '%E5%')
        ORDER BY line_name
        """
        
        result = client.query(mdm_query)
        
        if result.result_rows:
            print("✅ 在 MDM 維度表中找到匹配的維度組合：")
            df_mdm = pd.DataFrame(result.result_rows, columns=result.column_names)
            for _, row in df_mdm.iterrows():
                print(f"   🏭 {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['line_code']}")
                print(f"      Line Name: {row['line_name']}")
                print(f"      Line Desc: {row['line_desc']}")
        else:
            print("❌ 在 MDM 維度表中沒有找到匹配的維度組合")
            
            # 檢查相近的組合
            print("\n🔍 檢查相近的維度組合...")
            similar_query = """
            SELECT DISTINCT
                region_code,
                plant_code,
                factory_code,
                line_code,
                line_name
            FROM silver.dim_mfg_five_level
            WHERE (region_code = 'CNE' OR plant_code = 'WJ2' OR factory_code = 'NBU' OR line_name LIKE '%E5%')
            ORDER BY region_code, plant_code, factory_code, line_code
            LIMIT 20
            """
            
            similar_result = client.query(similar_query)
            if similar_result.result_rows:
                df_similar = pd.DataFrame(similar_result.result_rows, columns=similar_result.column_names)
                print("📋 相近的維度組合：")
                for _, row in df_similar.iterrows():
                    print(f"   {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['line_code']} ({row['line_name']})")
        
        # 2. 檢查 Gold 表中的實際資料
        print("\n📊 步驟 2：檢查 Gold 表中的實際資料")
        gold_query = """
        SELECT DISTINCT
            region_code,
            region_name,
            plant_code,
            plant_name,
            factory_code,
            factory_name,
            line_code,
            line_name,
            vx_type,
            count() as record_count
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
        WHERE (
            (region_code = 'CNE' OR region_name = 'CNE') AND
            (plant_code = 'WJ2' OR plant_name = 'WJ2' OR plant = 'WJ2') AND
            (factory_code = 'NBU' OR factory_name = 'NBU' OR factory = 'NBU') AND
            (line_code = 'E5' OR line_name = 'E5' OR line = 'E5')
        )
        GROUP BY region_code, region_name, plant_code, plant_name, factory_code, factory_name, line_code, line_name, vx_type
        ORDER BY record_count DESC
        """
        
        gold_result = client.query(gold_query)
        
        if gold_result.result_rows:
            print("✅ 在 Gold 表中找到匹配的維度組合：")
            df_gold = pd.DataFrame(gold_result.result_rows, columns=gold_result.column_names)
            for _, row in df_gold.iterrows():
                print(f"   🏭 {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['line_code']} ({row['vx_type']})")
                print(f"      記錄數: {row['record_count']}")
        else:
            print("❌ 在 Gold 表中沒有找到匹配的維度組合")
        
        # 3. 檢查原始 MDM 表格的資料
        print("\n📊 步驟 3：檢查原始 MDM 表格")
        
        # 檢查 line_desc_master 表
        line_query = """
        SELECT DISTINCT
            LINE_NAME,
            LINE_DESC,
            PROD_AREA_ID
        FROM bronze.common_mdm_line_desc_master
        WHERE LINE_NAME = 'E5' OR LINE_NAME LIKE '%E5%'
        ORDER BY LINE_NAME
        LIMIT 10
        """
        
        line_result = client.query(line_query)
        if line_result.result_rows:
            print("✅ 在 LINE 主檔中找到 E5 相關資料：")
            df_line = pd.DataFrame(line_result.result_rows, columns=line_result.column_names)
            for _, row in df_line.iterrows():
                print(f"   📍 Line: {row['LINE_NAME']} ({row['LINE_DESC']}) - PROD_AREA_ID: {row['PROD_AREA_ID']}")
                
                # 查找對應的 Factory
                if row['PROD_AREA_ID']:
                    factory_query = f"""
                    SELECT FACTORY, PROD_AREA_CODE, PROD_AREA_DESC
                    FROM bronze.common_mdm_prod_area_master
                    WHERE PROD_AREA_ID = {row['PROD_AREA_ID']}
                    """
                    
                    factory_result = client.query(factory_query)
                    if factory_result.result_rows:
                        factory_row = factory_result.result_rows[0]
                        print(f"      🏭 Factory: {factory_row[0]} ({factory_row[2]})")
                        
                        # 查找對應的 Plant
                        plant_query = f"""
                        SELECT MFG_PLANT_CODE, MFG_PLANT_DESC
                        FROM bronze.common_mdm_mfg_plant_master
                        WHERE FACTORY = '{factory_row[0]}'
                        """
                        
                        plant_result = client.query(plant_query)
                        if plant_result.result_rows:
                            plant_row = plant_result.result_rows[0]
                            print(f"         🏢 Plant: {plant_row[0]} ({plant_row[1]})")
                            
                            # 查找對應的 Region
                            region_query = f"""
                            SELECT fa.MFG_SITE, ms.MFG_SITE_DESC
                            FROM bronze.common_mdm_factory_area_master fa
                            LEFT JOIN bronze.common_mdm_mfg_site_master ms ON fa.MFG_SITE = ms.MFG_SITE
                            WHERE fa.FACTORY = '{factory_row[0]}'
                            """
                            
                            region_result = client.query(region_query)
                            if region_result.result_rows:
                                region_row = region_result.result_rows[0]
                                print(f"            🌏 Region: {region_row[0]} ({region_row[1]})")
                                
                                # 檢查是否符合 CNE-WJ2-NBU-E5 的模式
                                if (region_row[0] == 'CNE' and 
                                    plant_row[0] == 'WJ2' and 
                                    factory_row[0] == 'NBU'):
                                    print(f"               ✅ 找到完全匹配的維度組合！")
                                    
                                    # 查詢這個組合的任務資料
                                    task_query = f"""
                                    SELECT 
                                        snapshot_date,
                                        vx_type,
                                        sum_total_task_qty,
                                        sum_todo_qty,
                                        sum_doing_qty,
                                        sum_done_qty,
                                        completion_rate
                                    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
                                    WHERE region_code = 'CNE'
                                      AND plant_code = 'WJ2'
                                      AND factory_code = 'NBU'
                                      AND line_code = '{row['LINE_NAME']}'
                                      AND snapshot_date >= '2025-12-25'
                                      AND snapshot_date <= '2025-12-31'
                                    ORDER BY snapshot_date, vx_type
                                    """
                                    
                                    task_result = client.query(task_query)
                                    if task_result.result_rows:
                                        print(f"\n📊 找到任務資料：")
                                        df_task = pd.DataFrame(task_result.result_rows, columns=task_result.column_names)
                                        for _, task_row in df_task.iterrows():
                                            print(f"   📅 {task_row['snapshot_date']} {task_row['vx_type']}: Total={task_row['sum_total_task_qty']}, Todo={task_row['sum_todo_qty']}, Doing={task_row['sum_doing_qty']}, Done={task_row['sum_done_qty']}, Rate={task_row['completion_rate']:.1f}%")
        else:
            print("❌ 在 LINE 主檔中沒有找到 E5 相關資料")
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

if __name__ == "__main__":
    main()