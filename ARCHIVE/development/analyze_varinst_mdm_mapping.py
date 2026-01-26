#!/usr/bin/env python3
"""
分析 varinst 和 MDM 表的映射關係
產出 mapping 規格表和驗證 SQL
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 分析 varinst 和 MDM 表的映射關係")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 檢查 varinst 中的測試值
        print("📊 步驟 1：檢查 varinst 中的測試值 ('WJ2','NBU','E5','CNE')")
        varinst_query = """
        SELECT DISTINCT 
            NAME_,
            TEXT_,
            count() as occurrence_count
        FROM bronze.bpm_act_hi_varinst 
        WHERE TEXT_ IN ('WJ2','NBU','E5','CNE')
        GROUP BY NAME_, TEXT_
        ORDER BY NAME_, TEXT_
        """
        
        varinst_result = client.query(varinst_query)
        if varinst_result.result_rows:
            print("✅ 在 varinst 中找到測試值：")
            df_varinst = pd.DataFrame(varinst_result.result_rows, columns=varinst_result.column_names)
            for _, row in df_varinst.iterrows():
                print(f"   NAME_='{row['NAME_']}', TEXT_='{row['TEXT_']}' (出現 {row['occurrence_count']} 次)")
        else:
            print("❌ 在 varinst 中沒有找到測試值")
        
        # 2. 檢查 MDM 表中的對應值
        print("\n📊 步驟 2：檢查 MDM 表中的對應值")
        
        # 檢查 MFG_SITE (region)
        print("\n🔍 檢查 MFG_SITE (region)...")
        region_query = """
        SELECT MFG_SITE, MFG_SITE_DESC, count() as count
        FROM bronze.common_mdm_mfg_site_master
        WHERE MFG_SITE = 'CNE'
        GROUP BY MFG_SITE, MFG_SITE_DESC
        """
        region_result = client.query(region_query)
        if region_result.result_rows:
            for row in region_result.result_rows:
                print(f"   MFG_SITE: {row[0]} ({row[1]})")
        
        # 檢查 MFG_PLANT_CODE (plant)
        print("\n🔍 檢查 MFG_PLANT_CODE (plant)...")
        plant_query = """
        SELECT MFG_PLANT_CODE, MFG_PLANT_DESC, FACTORY, count() as count
        FROM bronze.common_mdm_mfg_plant_master
        WHERE MFG_PLANT_CODE = 'WJ2' AND VALIDITY = 'Y'
        GROUP BY MFG_PLANT_CODE, MFG_PLANT_DESC, FACTORY
        """
        plant_result = client.query(plant_query)
        if plant_result.result_rows:
            for row in plant_result.result_rows:
                print(f"   MFG_PLANT_CODE: {row[0]} ({row[1]}) -> FACTORY: {row[2]}")
        
        # 檢查 FACTORY (factory)
        print("\n🔍 檢查 FACTORY (factory)...")
        factory_query = """
        SELECT FACTORY, PROD_AREA_DESC, count() as count
        FROM bronze.common_mdm_prod_area_master
        WHERE FACTORY = 'NBU'
        GROUP BY FACTORY, PROD_AREA_DESC
        """
        factory_result = client.query(factory_query)
        if factory_result.result_rows:
            for row in factory_result.result_rows:
                print(f"   FACTORY: {row[0]} ({row[1]})")
        
        # 檢查 LINE_NAME (line)
        print("\n🔍 檢查 LINE_NAME (line)...")
        line_query = """
        SELECT LINE_NAME, LINE_DESC, PROD_AREA_ID, count() as count
        FROM bronze.common_mdm_line_desc_master
        WHERE LINE_NAME = 'E5' AND VALID_FLAG = 'Y'
        GROUP BY LINE_NAME, LINE_DESC, PROD_AREA_ID
        """
        line_result = client.query(line_query)
        if line_result.result_rows:
            for row in line_result.result_rows:
                print(f"   LINE_NAME: {row[0]} ({row[1]}) -> PROD_AREA_ID: {row[2]}")
        
        # 3. 檢查完整的串接路徑
        print("\n📊 步驟 3：檢查完整的串接路徑")
        full_mapping_query = """
        WITH full_mapping AS (
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
            WHERE l.VALID_FLAG = 'Y'
        )
        SELECT * FROM full_mapping
        WHERE LINE_NAME = 'E5'
           OR factory_code = 'NBU'
           OR plant_code = 'WJ2'
           OR region_code = 'CNE'
        ORDER BY region_code, plant_code, factory_code, LINE_NAME
        """
        
        full_result = client.query(full_mapping_query)
        if full_result.result_rows:
            print("✅ 完整串接結果：")
            df_full = pd.DataFrame(full_result.result_rows, columns=full_result.column_names)
            for _, row in df_full.iterrows():
                print(f"   {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['LINE_NAME']}")
                print(f"      Region: {row['region_code']} ({row['region_name']})")
                print(f"      Plant: {row['plant_code']} ({row['plant_name']})")
                print(f"      Factory: {row['factory_code']} ({row['factory_name']})")
                print(f"      Line: {row['LINE_NAME']} ({row['LINE_DESC']})")
                print()
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

if __name__ == "__main__":
    main()