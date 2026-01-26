#!/usr/bin/env python3
"""
從 Bronze 層 MDM 表中找出完全匹配的維度組合
目標：Region=CNE, Plant=WJ2, Factory=NBU, Line=N5
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 從 Bronze 層 MDM 表中尋找完全匹配的維度組合")
    print("目標：Region=CNE, Plant=WJ2, Factory=NBU, Line=N5")
    print("=" * 80)
    
    # ClickHouse 連線設定
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 先檢查所有 MDM 表的結構和內容
        print("📊 步驟 1：檢查 MDM 表結構")
        
        # 檢查 Line 表
        print("\n🔍 檢查 Line 主檔表...")
        line_query = """
        SELECT 
            LINE_NAME,
            LINE_DESC,
            PROD_AREA_ID,
            VALID_FLAG
        FROM bronze.common_mdm_line_desc_master
        WHERE LINE_NAME = 'N5'
        ORDER BY LINE_NAME
        """
        
        line_result = client.query(line_query)
        if line_result.result_rows:
            print("✅ 找到 N5 產線：")
            df_line = pd.DataFrame(line_result.result_rows, columns=line_result.column_names)
            for _, row in df_line.iterrows():
                print(f"   📍 Line: {row['LINE_NAME']} ({row['LINE_DESC']}) - PROD_AREA_ID: {row['PROD_AREA_ID']} - Valid: {row['VALID_FLAG']}")
                
                if row['PROD_AREA_ID']:
                    # 2. 從 PROD_AREA_ID 找到 Factory
                    print(f"\n🔍 步驟 2：從 PROD_AREA_ID {row['PROD_AREA_ID']} 找 Factory...")
                    factory_query = f"""
                    SELECT 
                        PROD_AREA_ID,
                        FACTORY,
                        PROD_AREA_CODE,
                        PROD_AREA_DESC
                    FROM bronze.common_mdm_prod_area_master
                    WHERE PROD_AREA_ID = {row['PROD_AREA_ID']}
                    """
                    
                    factory_result = client.query(factory_query)
                    if factory_result.result_rows:
                        factory_row = factory_result.result_rows[0]
                        print(f"   🏭 Factory: {factory_row[1]} ({factory_row[3]}) - PROD_AREA_CODE: {factory_row[2]}")
                        
                        # 檢查是否為 NBU
                        if factory_row[1] == 'NBU':
                            print(f"   ✅ 找到匹配的 Factory: NBU")
                            
                            # 3. 從 Factory 找到 Plant
                            print(f"\n🔍 步驟 3：從 Factory {factory_row[1]} 找 Plant...")
                            plant_query = f"""
                            SELECT 
                                FACTORY,
                                MFG_PLANT_CODE,
                                MFG_PLANT_DESC,
                                VALIDITY
                            FROM bronze.common_mdm_mfg_plant_master
                            WHERE FACTORY = '{factory_row[1]}'
                              AND VALIDITY = 'Y'
                            """
                            
                            plant_result = client.query(plant_query)
                            if plant_result.result_rows:
                                for plant_row in plant_result.result_rows:
                                    print(f"   🏢 Plant: {plant_row[1]} ({plant_row[2]}) - Valid: {plant_row[3]}")
                                    
                                    # 檢查是否為 WJ2
                                    if plant_row[1] == 'WJ2':
                                        print(f"   ✅ 找到匹配的 Plant: WJ2")
                                        
                                        # 4. 從 Factory 找到 Region
                                        print(f"\n🔍 步驟 4：從 Factory {factory_row[1]} 找 Region...")
                                        region_query = f"""
                                        SELECT 
                                            fa.FACTORY,
                                            fa.MFG_SITE,
                                            fa.COUNTRY,
                                            fa.VALID,
                                            ms.MFG_SITE_DESC
                                        FROM bronze.common_mdm_factory_area_master fa
                                        LEFT JOIN bronze.common_mdm_mfg_site_master ms ON fa.MFG_SITE = ms.MFG_SITE
                                        WHERE fa.FACTORY = '{factory_row[1]}'
                                          AND fa.VALID = '1'
                                        """
                                        
                                        region_result = client.query(region_query)
                                        if region_result.result_rows:
                                            for region_row in region_result.result_rows:
                                                print(f"   🌏 Region: {region_row[1]} ({region_row[4]}) - Country: {region_row[2]} - Valid: {region_row[3]}")
                                                
                                                # 檢查是否為 CNE
                                                if region_row[1] == 'CNE':
                                                    print(f"\n🎉 找到完全匹配的維度組合！")
                                                    print(f"   Region: {region_row[1]} ({region_row[4]})")
                                                    print(f"   Plant: {plant_row[1]} ({plant_row[2]})")
                                                    print(f"   Factory: {factory_row[1]} ({factory_row[3]})")
                                                    print(f"   Line: {row['LINE_NAME']} ({row['LINE_DESC']})")
                                                    
                                                    # 5. 檢查這個組合在 Gold 表中是否有資料
                                                    print(f"\n🔍 步驟 5：檢查 Gold 表中的任務資料...")
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
                                                    WHERE region_code = '{region_row[1]}'
                                                      AND plant_code = '{plant_row[1]}'
                                                      AND factory_code = '{factory_row[1]}'
                                                      AND line_code = '{row['LINE_NAME']}'
                                                      AND snapshot_date >= '2025-12-25'
                                                      AND snapshot_date <= '2025-12-31'
                                                    ORDER BY snapshot_date, vx_type
                                                    """
                                                    
                                                    task_result = client.query(task_query)
                                                    if task_result.result_rows:
                                                        print(f"✅ 找到任務資料：")
                                                        df_task = pd.DataFrame(task_result.result_rows, columns=task_result.column_names)
                                                        for _, task_row in df_task.iterrows():
                                                            print(f"   📅 {task_row['snapshot_date']} {task_row['vx_type']}: Total={task_row['sum_total_task_qty']}, Todo={task_row['sum_todo_qty']}, Doing={task_row['sum_doing_qty']}, Done={task_row['sum_done_qty']}, Rate={task_row['completion_rate']:.1f}%")
                                                    else:
                                                        print(f"❌ 在 Gold 表中沒有找到對應的任務資料")
                                                        
                                                        # 檢查是否有其他類似的組合
                                                        print(f"\n🔍 檢查 Gold 表中是否有其他相關組合...")
                                                        similar_query = f"""
                                                        SELECT DISTINCT
                                                            region_code,
                                                            plant_code,
                                                            factory_code,
                                                            line_code,
                                                            vx_type,
                                                            count() as record_count
                                                        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
                                                        WHERE (region_code = '{region_row[1]}' OR 
                                                               plant_code = '{plant_row[1]}' OR 
                                                               factory_code = '{factory_row[1]}' OR 
                                                               line_code = '{row['LINE_NAME']}')
                                                        GROUP BY region_code, plant_code, factory_code, line_code, vx_type
                                                        ORDER BY record_count DESC
                                                        LIMIT 10
                                                        """
                                                        
                                                        similar_result = client.query(similar_query)
                                                        if similar_result.result_rows:
                                                            print(f"📋 相關的維度組合：")
                                                            df_similar = pd.DataFrame(similar_result.result_rows, columns=similar_result.column_names)
                                                            for _, sim_row in df_similar.iterrows():
                                                                print(f"   {sim_row['region_code']}-{sim_row['plant_code']}-{sim_row['factory_code']}-{sim_row['line_code']} ({sim_row['vx_type']}) - 記錄數: {sim_row['record_count']}")
                                                else:
                                                    print(f"   ❌ Region {region_row[1]} 不匹配 CNE")
                                        else:
                                            print(f"   ❌ Factory {factory_row[1]} 沒有對應的 Region 資料")
                                    else:
                                        print(f"   ❌ Plant {plant_row[1]} 不匹配 WJ2")
                            else:
                                print(f"   ❌ Factory {factory_row[1]} 沒有對應的 Plant 資料")
                        else:
                            print(f"   ❌ Factory {factory_row[1]} 不匹配 NBU")
                    else:
                        print(f"   ❌ PROD_AREA_ID {row['PROD_AREA_ID']} 沒有對應的 Factory 資料")
        else:
            print("❌ 沒有找到 N5 產線")
            
            # 檢查是否有其他 N 開頭的產線
            print("\n🔍 檢查其他 N 開頭的產線...")
            n_lines_query = """
            SELECT DISTINCT
                LINE_NAME,
                LINE_DESC,
                PROD_AREA_ID
            FROM bronze.common_mdm_line_desc_master
            WHERE LINE_NAME LIKE 'N%'
              AND VALID_FLAG = 'Y'
            ORDER BY LINE_NAME
            LIMIT 20
            """
            
            n_lines_result = client.query(n_lines_query)
            if n_lines_result.result_rows:
                print("📋 找到的 N 開頭產線：")
                df_n_lines = pd.DataFrame(n_lines_result.result_rows, columns=n_lines_result.column_names)
                for _, row in df_n_lines.iterrows():
                    print(f"   {row['LINE_NAME']} ({row['LINE_DESC']}) - PROD_AREA_ID: {row['PROD_AREA_ID']}")
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

if __name__ == "__main__":
    main()