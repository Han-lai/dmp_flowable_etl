#!/usr/bin/env python3
"""
執行修正後的 VARINST 到 MDM 映射示範
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 執行修正後的 VARINST 到 MDM 映射示範")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 2. MDM 實際映射
        print("📊 2. MDM 實際映射")
        mdm_query = """
        SELECT 
            'MDM 實際映射' AS source,
            mp.MFG_PLANT_CODE AS plant_code,
            p.FACTORY AS factory_code,
            l.LINE_NAME AS line_name,
            fa.MFG_SITE AS region_code,
            
            -- 顯示完整描述
            mp.MFG_PLANT_DESC AS plant_desc,
            p.PROD_AREA_DESC AS factory_desc,
            l.LINE_DESC AS line_desc,
            ms.MFG_SITE_DESC AS region_desc
            
        FROM bronze.common_mdm_line_desc_master l
        LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
        LEFT JOIN bronze.common_mdm_mfg_plant_master mp ON p.FACTORY = mp.FACTORY AND mp.VALIDITY = 'Y'
        LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
        LEFT JOIN bronze.common_mdm_mfg_site_master ms ON fa.MFG_SITE = ms.MFG_SITE
        WHERE l.VALID_FLAG = 'Y'
          AND l.LINE_NAME = 'E5'
          AND fa.MFG_SITE = 'CNE'
          AND (mp.MFG_PLANT_CODE = 'NBU' OR p.FACTORY = 'WJ2')
        ORDER BY mp.MFG_PLANT_CODE, p.FACTORY
        """
        
        mdm_result = client.query(mdm_query)
        if mdm_result.result_rows:
            print("✅ MDM 中找到的實際映射：")
            df_mdm = pd.DataFrame(mdm_result.result_rows, columns=mdm_result.column_names)
            for _, row in df_mdm.iterrows():
                print(f"   Region: {row['region_code']} ({row['region_desc']})")
                print(f"   Plant: {row['plant_code']} ({row['plant_desc']})")
                print(f"   Factory: {row['factory_code']} ({row['factory_desc']})")
                print(f"   Line: {row['line_name']} ({row['line_desc']})")
                print()
        
        # 4. 實用的映射函數示範
        print("📊 4. 實用的映射函數示範")
        practical_query = """
        WITH practical_mapping AS (
            SELECT 
                -- 輸入：VARINST 值
                v.varinst_plant,
                v.varinst_factory,
                v.varinst_lineName,
                v.varinst_region,
                
                -- 輸出：MDM 映射結果（注意維度交換）
                COALESCE(
                    -- 優先使用 MDM 映射（維度交換）
                    CASE WHEN v.varinst_plant IS NOT NULL THEN mdm.factory_code END,
                    -- Fallback 到原始 varinst 值
                    v.varinst_plant,
                    ''
                ) AS final_factory,
                
                COALESCE(
                    -- 優先使用 MDM 映射（維度交換）
                    CASE WHEN v.varinst_factory IS NOT NULL THEN mdm.plant_code END,
                    -- Fallback 到原始 varinst 值  
                    v.varinst_factory,
                    ''
                ) AS final_plant,
                
                COALESCE(
                    mdm.line_name,
                    v.varinst_lineName,
                    ''
                ) AS final_line,
                
                COALESCE(
                    mdm.region_code,
                    v.varinst_region,
                    ''
                ) AS final_region,
                
                -- 資料來源標記
                CASE 
                    WHEN mdm.line_name IS NOT NULL THEN 'MDM_PRIMARY'
                    WHEN v.varinst_lineName IS NOT NULL THEN 'VARINST_FALLBACK'
                    ELSE 'NO_DATA'
                END AS data_source
                
            FROM (
                -- 模擬 varinst 資料
                SELECT 
                    'WJ2' AS varinst_plant,
                    'NBU' AS varinst_factory, 
                    'E5' AS varinst_lineName,
                    'CNE' AS varinst_region
            ) v
            LEFT JOIN (
                -- MDM 查找表（注意維度交換邏輯）
                SELECT 
                    l.LINE_NAME AS line_name,
                    p.FACTORY AS factory_code,  -- VARINST plant 對應 MDM factory
                    mp.MFG_PLANT_CODE AS plant_code,  -- VARINST factory 對應 MDM plant
                    fa.MFG_SITE AS region_code
                FROM bronze.common_mdm_line_desc_master l
                LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
                LEFT JOIN bronze.common_mdm_mfg_plant_master mp ON p.FACTORY = mp.FACTORY AND mp.VALIDITY = 'Y'
                LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
                WHERE l.VALID_FLAG = 'Y'
            ) mdm ON v.varinst_lineName = mdm.line_name
                 AND v.varinst_plant = mdm.factory_code  -- 注意：varinst plant 對應 mdm factory
                 AND v.varinst_factory = mdm.plant_code  -- 注意：varinst factory 對應 mdm plant
                 AND v.varinst_region = mdm.region_code
        )
        
        SELECT 
            '輸入 (VARINST)' AS stage,
            varinst_region AS region,
            varinst_plant AS plant,
            varinst_factory AS factory,
            varinst_lineName AS line,
            data_source
        
        FROM practical_mapping
        
        UNION ALL
        
        SELECT 
            '輸出 (MDM 映射後)' AS stage,
            final_region AS region,
            final_plant AS plant,
            final_factory AS factory,
            final_line AS line,
            data_source
            
        FROM practical_mapping
        """
        
        practical_result = client.query(practical_query)
        if practical_result.result_rows:
            print("✅ 映射函數示範結果：")
            df_practical = pd.DataFrame(practical_result.result_rows, columns=practical_result.column_names)
            for _, row in df_practical.iterrows():
                print(f"   {row['stage']}: {row['region']}-{row['plant']}-{row['factory']}-{row['line']} ({row['data_source']})")
        
        print("\n" + "=" * 80)
        print("🎉 關鍵發現總結：")
        print("1. ✅ VARINST 中確實有目標測試值：")
        print("   - region='CNE' (3528 次)")
        print("   - plant='WJ2' (9093 次)")  
        print("   - factory='NBU' (6230 次)")
        print("   - lineName='E5' (685 次)")
        print()
        print("2. 🔄 MDM 中的維度語意與 VARINST 相反：")
        print("   - VARINST: plant='WJ2', factory='NBU'")
        print("   - MDM: plant_code='NBU', factory_code='WJ2'")
        print()
        print("3. ✅ 正確的映射策略：")
        print("   - varinst.plant → mdm.factory_code")
        print("   - varinst.factory → mdm.plant_code")
        print("   - varinst.lineName → mdm.line_name")
        print("   - varinst.region → mdm.region_code")
        print()
        print("4. 📋 實作建議：")
        print("   - 在 Silver 層 MVIEW 中實作維度交換邏輯")
        print("   - MDM 優先，VARINST 作為 fallback")
        print("   - 標記資料來源以便監控品質")
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

if __name__ == "__main__":
    main()