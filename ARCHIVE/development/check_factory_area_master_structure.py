#!/usr/bin/env python3
"""
檢查 bronze.common_mdm_factory_area_master 表結構
確認是否可以直接從 FACTORY 得到 MFG_SITE
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 檢查 bronze.common_mdm_factory_area_master 表結構")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 檢查表結構
        print("📊 步驟 1：檢查表結構")
        structure_query = """
        DESCRIBE bronze.common_mdm_factory_area_master
        """
        
        structure_result = client.query(structure_query)
        if structure_result.result_rows:
            print("✅ 表結構：")
            df_structure = pd.DataFrame(structure_result.result_rows, columns=structure_result.column_names)
            for _, row in df_structure.iterrows():
                print(f"   {row['name']}: {row['type']}")
        
        # 2. 檢查是否包含 FACTORY 和 MFG_SITE 欄位
        print("\n📊 步驟 2：檢查關鍵欄位內容")
        content_query = """
        SELECT 
            FACTORY,
            MFG_SITE,
            VALID,
            count() as record_count
        FROM bronze.common_mdm_factory_area_master
        WHERE FACTORY IN ('WJ2', 'NBU') OR MFG_SITE = 'CNE'
        GROUP BY FACTORY, MFG_SITE, VALID
        ORDER BY FACTORY, MFG_SITE
        """
        
        content_result = client.query(content_query)
        if content_result.result_rows:
            print("✅ 關鍵欄位內容：")
            df_content = pd.DataFrame(content_result.result_rows, columns=content_result.column_names)
            for _, row in df_content.iterrows():
                print(f"   FACTORY: {row['FACTORY']}, MFG_SITE: {row['MFG_SITE']}, VALID: {row['VALID']}, 記錄數: {row['record_count']}")
        
        # 3. 驗證直接串接的可行性
        print("\n📊 步驟 3：驗證直接串接的可行性")
        direct_join_query = """
        SELECT 
            l.LINE_NAME,
            p.FACTORY,
            fa.MFG_SITE,
            fa.VALID as factory_area_valid,
            count() as combination_count
        FROM bronze.common_mdm_line_desc_master l
        LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
        LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY
        WHERE l.VALID_FLAG = 'Y'
          AND l.LINE_NAME = 'E5'
          AND p.FACTORY = 'WJ2'
          AND fa.MFG_SITE = 'CNE'
        GROUP BY l.LINE_NAME, p.FACTORY, fa.MFG_SITE, fa.VALID
        ORDER BY combination_count DESC
        """
        
        direct_result = client.query(direct_join_query)
        if direct_result.result_rows:
            print("✅ 直接串接結果：")
            df_direct = pd.DataFrame(direct_result.result_rows, columns=direct_result.column_names)
            print(f"   欄位名稱: {list(df_direct.columns)}")
            for _, row in df_direct.iterrows():
                print(f"   結果: {dict(row)}")
        else:
            print("❌ 直接串接沒有找到結果")
        
        # 4. 比較原始的三步串接 vs 簡化的兩步串接
        print("\n📊 步驟 4：比較串接方式")
        
        # 原始三步串接
        three_step_query = """
        SELECT 
            'three_step' as method,
            l.LINE_NAME,
            p.FACTORY,
            fa.MFG_SITE,
            ms.MFG_SITE_DESC,
            count() as result_count
        FROM bronze.common_mdm_line_desc_master l
        LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
        LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
        LEFT JOIN bronze.common_mdm_mfg_site_master ms ON fa.MFG_SITE = ms.MFG_SITE
        WHERE l.VALID_FLAG = 'Y' AND l.LINE_NAME = 'E5' AND p.FACTORY = 'WJ2' AND fa.MFG_SITE = 'CNE'
        GROUP BY l.LINE_NAME, p.FACTORY, fa.MFG_SITE, ms.MFG_SITE_DESC
        """
        
        # 簡化兩步串接
        two_step_query = """
        SELECT 
            'two_step' as method,
            l.LINE_NAME,
            p.FACTORY,
            fa.MFG_SITE,
            fa.MFG_SITE as MFG_SITE_DESC,  -- 假設不需要描述
            count() as result_count
        FROM bronze.common_mdm_line_desc_master l
        LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
        LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
        WHERE l.VALID_FLAG = 'Y' AND l.LINE_NAME = 'E5' AND p.FACTORY = 'WJ2' AND fa.MFG_SITE = 'CNE'
        GROUP BY l.LINE_NAME, p.FACTORY, fa.MFG_SITE
        """
        
        print("   🔍 三步串接結果：")
        three_step_result = client.query(three_step_query)
        if three_step_result.result_rows:
            df_three = pd.DataFrame(three_step_result.result_rows, columns=three_step_result.column_names)
            print(f"      欄位名稱: {list(df_three.columns)}")
            for _, row in df_three.iterrows():
                print(f"      結果: {dict(row)}")
        else:
            print("      ❌ 三步串接無結果")
        
        print("   🔍 兩步串接結果：")
        two_step_result = client.query(two_step_query)
        if two_step_result.result_rows:
            df_two = pd.DataFrame(two_step_result.result_rows, columns=two_step_result.column_names)
            print(f"      欄位名稱: {list(df_two.columns)}")
            for _, row in df_two.iterrows():
                print(f"      結果: {dict(row)}")
        else:
            print("      ❌ 兩步串接無結果")
        
        # 5. 檢查是否需要 MFG_SITE_DESC
        print("\n📊 步驟 5：檢查是否需要 MFG_SITE_DESC")
        desc_check_query = """
        SELECT 
            fa.MFG_SITE,
            ms.MFG_SITE_DESC,
            CASE WHEN fa.MFG_SITE = ms.MFG_SITE_DESC THEN '相同' ELSE '不同' END as comparison
        FROM bronze.common_mdm_factory_area_master fa
        LEFT JOIN bronze.common_mdm_mfg_site_master ms ON fa.MFG_SITE = ms.MFG_SITE
        WHERE fa.MFG_SITE = 'CNE'
        LIMIT 5
        """
        
        desc_result = client.query(desc_check_query)
        if desc_result.result_rows:
            print("✅ MFG_SITE vs MFG_SITE_DESC 比較：")
            df_desc = pd.DataFrame(desc_result.result_rows, columns=desc_result.column_names)
            print(f"   欄位名稱: {list(df_desc.columns)}")
            for _, row in df_desc.iterrows():
                print(f"   結果: {dict(row)}")
        else:
            print("❌ 無法取得 MFG_SITE_DESC 比較結果")
        
        print("\n" + "=" * 80)
        print("📋 結論：")
        
        # 檢查兩步串接是否可行
        if two_step_result.result_rows and len(two_step_result.result_rows) > 0:
            print("✅ 可以簡化為兩步串接：")
            print("   1. Line → Factory: line_desc_master.PROD_AREA_ID → prod_area_master.FACTORY")
            print("   2. Factory → Region: prod_area_master.FACTORY → factory_area_master.MFG_SITE")
            print("   ✅ bronze.common_mdm_factory_area_master 表確實包含 FACTORY 和 MFG_SITE")
        else:
            print("❌ 無法簡化為兩步串接，仍需要三步串接")
        
        # 檢查是否需要 MFG_SITE_DESC
        if desc_result.result_rows:
            need_desc = any(row[2] == '不同' for row in desc_result.result_rows)
            if need_desc:
                print("⚠️  需要保留 MFG_SITE_DESC，因為與 MFG_SITE 不同")
            else:
                print("✅ 可以省略 MFG_SITE_DESC，因為與 MFG_SITE 相同")
        
    except Exception as e:
        print(f"❌ 查詢失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

if __name__ == "__main__":
    main()