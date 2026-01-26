#!/usr/bin/env python3
"""
從 Bronze 層 MDM 表中尋找完全匹配的 CNE-WJ2-NBU-E5 維度組合
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 尋找完全匹配的 CNE-WJ2-NBU-E5 維度組合")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 方法1：從 E5 產線開始向上查找
        print("📊 方法1：從 E5 產線開始查找...")
        e5_query = """
        WITH line_to_region AS (
            SELECT 
                l.LINE_NAME,
                l.LINE_DESC,
                l.PROD_AREA_ID,
                p.FACTORY as factory_code,
                p.PROD_AREA_DESC as factory_name,
                mp.MFG_PLANT_CODE as plant_code,
                mp.MFG_PLANT_DESC as plant_name,
                fa.MFG_SITE as region_code,
                ms.MFG_SITE_DESC as region_name
            FROM bronze.common_mdm_line_desc_master l
            LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
            LEFT JOIN bronze.common_mdm_mfg_plant_master mp ON p.FACTORY = mp.FACTORY AND mp.VALIDITY = 'Y'
            LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
            LEFT JOIN bronze.common_mdm_mfg_site_master ms ON fa.MFG_SITE = ms.MFG_SITE
            WHERE l.LINE_NAME = 'E5' AND l.VALID_FLAG = 'Y'
        )
        SELECT * FROM line_to_region
        WHERE region_code = 'CNE' 
          AND plant_code = 'WJ2' 
          AND factory_code = 'NBU'
        """
        
        result = client.query(e5_query)
        if result.result_rows:
            print("✅ 找到完全匹配的 CNE-WJ2-NBU-E5 組合：")
            df = pd.DataFrame(result.result_rows, columns=result.column_names)
            for _, row in df.iterrows():
                print(f"   🎉 完整匹配：")
                print(f"      Region: {row['region_code']} ({row['region_name']})")
                print(f"      Plant: {row['plant_code']} ({row['plant_name']})")
                print(f"      Factory: {row['factory_code']} ({row['factory_name']})")
                print(f"      Line: {row['LINE_NAME']} ({row['LINE_DESC']})")
        else:
            print("❌ 沒有找到完全匹配的組合")
            
            # 檢查部分匹配
            print("\n🔍 檢查部分匹配的組合...")
            partial_query = """
            WITH line_to_region AS (
                SELECT 
                    l.LINE_NAME,
                    l.PROD_AREA_ID,
                    p.FACTORY as factory_code,
                    mp.MFG_PLANT_CODE as plant_code,
                    fa.MFG_SITE as region_code
                FROM bronze.common_mdm_line_desc_master l
                LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
                LEFT JOIN bronze.common_mdm_mfg_plant_master mp ON p.FACTORY = mp.FACTORY AND mp.VALIDITY = 'Y'
                LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
                WHERE l.LINE_NAME = 'E5' AND l.VALID_FLAG = 'Y'
            )
            SELECT * FROM line_to_region
            """
            
            partial_result = client.query(partial_query)
            if partial_result.result_rows:
                print("📋 E5 產線的所有組合：")
                df_partial = pd.DataFrame(partial_result.result_rows, columns=partial_result.column_names)
                for _, row in df_partial.iterrows():
                    match_status = []
                    if row['region_code'] == 'CNE': match_status.append("✅Region")
                    else: match_status.append("❌Region")
                    if row['plant_code'] == 'WJ2': match_status.append("✅Plant")
                    else: match_status.append("❌Plant")
                    if row['factory_code'] == 'NBU': match_status.append("✅Factory")
                    else: match_status.append("❌Factory")
                    
                    print(f"   {row['region_code']}-{row['plant_code']}-{row['factory_code']}-E5 {' '.join(match_status)}")
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

if __name__ == "__main__":
    main()