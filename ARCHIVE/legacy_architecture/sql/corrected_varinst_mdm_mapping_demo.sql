-- ========================================
-- 修正後的 VARINST 到 MDM 映射示範
-- ========================================
-- 重要發現：VARINST 和 MDM 的維度語意不一致
-- VARINST: plant='WJ2', factory='NBU'
-- MDM: plant_code='NBU', factory_code='WJ2'

-- ========================================
-- 1. 展示 VARINST 中的原始語意
-- ========================================
SELECT '1. VARINST 原始語意' AS section;

SELECT 
    'VARINST 語意' AS source,
    'WJ2' AS plant_value,
    'NBU' AS factory_value,
    'E5' AS line_value,
    'CNE' AS region_value;

-- ========================================
-- 2. 展示 MDM 中的實際映射
-- ========================================
SELECT '2. MDM 實際映射' AS section;

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
ORDER BY mp.MFG_PLANT_CODE, p.FACTORY;

-- ========================================
-- 3. 正確的映射邏輯示範
-- ========================================
SELECT '3. 正確的映射邏輯' AS section;

WITH varinst_to_mdm_mapping AS (
    SELECT 
        -- VARINST 原始值
        'WJ2' AS varinst_plant,
        'NBU' AS varinst_factory,
        'E5' AS varinst_line,
        'CNE' AS varinst_region,
        
        -- MDM 對應邏輯（修正後）
        CASE 
            -- 如果 VARINST plant='WJ2'，在 MDM 中應該查找 factory_code='WJ2'
            WHEN 'WJ2' = p.FACTORY THEN p.FACTORY
            ELSE NULL
        END AS mdm_factory_code,
        
        CASE 
            -- 如果 VARINST factory='NBU'，在 MDM 中應該查找 plant_code='NBU'  
            WHEN 'NBU' = mp.MFG_PLANT_CODE THEN mp.MFG_PLANT_CODE
            ELSE NULL
        END AS mdm_plant_code,
        
        l.LINE_NAME AS mdm_line_name,
        fa.MFG_SITE AS mdm_region_code
        
    FROM bronze.common_mdm_line_desc_master l
    LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
    LEFT JOIN bronze.common_mdm_mfg_plant_master mp ON p.FACTORY = mp.FACTORY AND mp.VALIDITY = 'Y'
    LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
    WHERE l.VALID_FLAG = 'Y'
      AND l.LINE_NAME = 'E5'
      AND fa.MFG_SITE = 'CNE'
      AND p.FACTORY = 'WJ2'  -- VARINST plant='WJ2' 對應 MDM factory='WJ2'
      AND mp.MFG_PLANT_CODE = 'NBU'  -- VARINST factory='NBU' 對應 MDM plant='NBU'
)

SELECT 
    varinst_region,
    varinst_plant,
    varinst_factory,
    varinst_line,
    '→' AS arrow,
    mdm_region_code,
    mdm_plant_code,
    mdm_factory_code,
    mdm_line_name,
    
    CASE 
        WHEN mdm_region_code IS NOT NULL 
         AND mdm_plant_code IS NOT NULL 
         AND mdm_factory_code IS NOT NULL 
         AND mdm_line_name IS NOT NULL
        THEN '✅ 完整映射成功'
        ELSE '❌ 映射失敗'
    END AS mapping_result
    
FROM varinst_to_mdm_mapping;

-- ========================================
-- 4. 實用的映射函數示範
-- ========================================
SELECT '4. 實用的映射函數示範' AS section;

-- 這個查詢展示如何在實際應用中處理 VARINST 到 MDM 的映射
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
    
FROM practical_mapping;

-- ========================================
-- 5. 總結和建議
-- ========================================
SELECT '5. 總結和建議' AS section;

SELECT 
    '關鍵發現' AS item,
    'VARINST 和 MDM 的 plant/factory 維度語意相反' AS description
    
UNION ALL

SELECT 
    '映射策略' AS item,
    'varinst.plant → mdm.factory, varinst.factory → mdm.plant' AS description
    
UNION ALL

SELECT 
    '實作建議' AS item,
    '在 Silver 層 MVIEW 中實作維度交換邏輯' AS description
    
UNION ALL

SELECT 
    '資料品質' AS item,
    'MDM 優先，VARINST 作為 fallback，並標記資料來源' AS description;