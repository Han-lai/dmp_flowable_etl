#!/usr/bin/env python3
"""
檢查 NBU Factory 下有哪些產線
並檢查 CNE-WJ2-NBU 的完整組合
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 檢查 NBU Factory 下的所有產線")
    print("=" * 80)
    
    # ClickHouse 連線設定
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 先找到所有 NBU Factory 的 PROD_AREA_ID
        print("📊 步驟 1：找到所有 NBU Factory")
        nbu_factory_query = """
        SELECT 
            PROD_AREA_ID,
            FACTORY,
            PROD_AREA_CODE,
            PROD_AREA_DESC
        FROM bronze.common_mdm_prod_area_master
        WHERE FACTORY = 'NBU'
        ORDER BY PROD_AREA_ID
        """
        
        nbu_result = client.query(nbu_factory_query)
        if nbu_result.result_rows:
            print("✅ 找到 NBU Factory：")
            df_nbu = pd.DataFrame(nbu_result.result_rows, columns=nbu_result.column_names)
            
            for _, nbu_row in df_nbu.iterrows():
                print(f"   🏭 NBU Factory: PROD_AREA_ID={nbu_row['PROD_AREA_ID']}, CODE={nbu_row['PROD_AREA_CODE']}, DESC={nbu_row['PROD_AREA_DESC']}")
                
                # 2. 找到這個 NBU Factory 下的所有產線
                print(f"\n🔍 步驟 2：檢查 PROD_AREA_ID {nbu_row['PROD_AREA_ID']} 下的產線...")
                lines_query = f"""
                SELECT 
                    LINE_NAME,
                    LINE_DESC,
                    PROD_AREA_ID,
                    VALID_FLAG
                FROM bronze.common_mdm_line_desc_master
                WHERE PROD_AREA_ID = {nbu_row['PROD_AREA_ID']}
                  AND VALID_FLAG = 'Y'
                ORDER BY LINE_NAME
                """
                
                lines_result = client.query(lines_query)
                if lines_result.result_rows:
                    print(f"   📍 找到產線：")
                    df_lines = pd.DataFrame(lines_result.result_rows, columns=lines_result.column_names)
                    for _, line_row in df_lines.iterrows():
                        print(f"      Line: {line_row['LINE_NAME']} ({line_row['LINE_DESC']})")
                else:
                    print(f"   ❌ 沒有找到產線")
                
                # 3. 檢查這個 NBU Factory 對應的 Plant
                print(f"\n🔍 步驟 3：檢查 NBU Factory 對應的 Plant...")
                plant_query = f"""
                SELECT 
                    FACTORY,
                    MFG_PLANT_CODE,
                    MFG_PLANT_DESC,
                    VALIDITY
                FROM bronze.common_mdm_mfg_plant_master
                WHERE FACTORY = 'NBU'
                  AND VALIDITY = 'Y'
                """
                
                plant_result = client.query(plant_query)
                if plant_result.result_rows:
                    print(f"   🏢 找到 Plant：")
                    df_plant = pd.DataFrame(plant_result.result_rows, columns=plant_result.column_names)
                    for _, plant_row in df_plant.iterrows():
                        print(f"      Plant: {plant_row['MFG_PLANT_CODE']} ({plant_row['MFG_PLANT_DESC']})")
                        
                        # 檢查是否為 WJ2
                        if plant_row['MFG_PLANT_CODE'] == 'WJ2':
                            print(f"      ✅ 找到匹配的 Plant: WJ2")
                            
                            # 4. 檢查對應的 Region
                            print(f"\n🔍 步驟 4：檢查 NBU Factory 對應的 Region...")
                            region_query = f"""
                            SELECT 
                                fa.FACTORY,
                                fa.MFG_SITE,
                                fa.COUNTRY,
                                fa.VALID,
                                ms.MFG_SITE_DESC
                            FROM bronze.common_mdm_factory_area_master fa
                            LEFT JOIN bronze.common_mdm_mfg_site_master ms ON fa.MFG_SITE = ms.MFG_SITE
                            WHERE fa.FACTORY = 'NBU'
                              AND fa.VALID = '1'
                            """
                            
                            region_result = client.query(region_query)
                            if region_result.result_rows:
                                print(f"   🌏 找到 Region：")
                                df_region = pd.DataFrame(region_result.result_rows, columns=region_result.column_names)
                                for _, region_row in df_region.iterrows():
                                    print(f"      Region: {region_row['MFG_SITE']} ({region_row['MFG_SITE_DESC']}) - Country: {region_row['COUNTRY']}")
                                    
                                    # 檢查是否為 CNE
                                    if region_row['MFG_SITE'] == 'CNE':
                                        print(f"      ✅ 找到匹配的 Region: CNE")
                                        
                                        print(f"\n🎉 完整匹配的維度組合：")
                                        print(f"   Region: {region_row['MFG_SITE']} ({region_row['MFG_SITE_DESC']})")
                                        print(f"   Plant: {plant_row['MFG_PLANT_CODE']} ({plant_row['MFG_PLANT_DESC']})")
                                        print(f"   Factory: NBU ({nbu_row['PROD_AREA_DESC']})")
                                        
                                        # 顯示所有可用的產線
                                        if lines_result.result_rows:
                                            print(f"   可用產線：")
                                            for _, line_row in df_lines.iterrows():
                                                print(f"      - {line_row['LINE_NAME']} ({line_row['LINE_DESC']})")
                                                
                                                # 檢查每個產線在 Gold 表中是否有資料
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
                                                WHERE region_code = '{region_row['MFG_SITE']}'
                                                  AND plant_code = '{plant_row['MFG_PLANT_CODE']}'
                                                  AND factory_code = 'NBU'
                                                  AND line_code = '{line_row['LINE_NAME']}'
                                                  AND vx_type = 'V3'
                                                  AND snapshot_date >= '2025-12-25'
                                                  AND snapshot_date <= '2025-12-31'
                                                ORDER BY snapshot_date
                                                """
                                                
                                                task_result = client.query(task_query)
                                                if task_result.result_rows:
                                                    print(f"        ✅ 在 Gold 表中找到 V3 任務資料：")
                                                    df_task = pd.DataFrame(task_result.result_rows, columns=task_result.column_names)
                                                    for _, task_row in df_task.iterrows():
                                                        print(f"           📅 {task_row['snapshot_date']}: Total={task_row['sum_total_task_qty']}, Todo={task_row['sum_todo_qty']}, Doing={task_row['sum_doing_qty']}, Done={task_row['sum_done_qty']}, Rate={task_row['completion_rate']:.1f}%")
                                                else:
                                                    print(f"        ❌ 在 Gold 表中沒有找到 V3 任務資料")
                                    else:
                                        print(f"      ❌ Region {region_row['MFG_SITE']} 不匹配 CNE")
                            else:
                                print(f"   ❌ NBU Factory 沒有對應的 Region 資料")
                        else:
                            print(f"      ❌ Plant {plant_row['MFG_PLANT_CODE']} 不匹配 WJ2")
                else:
                    print(f"   ❌ NBU Factory 沒有對應的 Plant 資料")
                
                print(f"\n" + "=" * 60)
        else:
            print("❌ 沒有找到 NBU Factory")
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

if __name__ == "__main__":
    main()