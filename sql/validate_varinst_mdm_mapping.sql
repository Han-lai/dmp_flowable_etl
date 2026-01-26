-- ========================================
-- 驗證 VARINST 到 MDM 映射的 SQL
-- ========================================
-- 目的：驗證 MDM mapping 出來的維度與原本 varinst 語意一致
-- 測試值：'WJ2','NBU','E5','CNE'

-- ========================================
-- A. 用 varinst 驗證（原始邏輯的基準）
-- ========================================
-- 檢查 varinst 中的測試值分布

SELECT 'A. VARINST 原始邏輯驗證' AS validation_type;

SELECT 
    NAME_ AS dimension_name,
    TEXT_ AS dimension_value,
    count() AS occurrence_count,
    CASE 
        WHEN NAME_ = 'region' AND TEXT_ = 'CNE' THEN '✅ region=CNE'
        WHEN NAME_ = 'plant' AND TEXT_ = 'WJ2' THEN '✅ plant=WJ2'
        WHEN NAME_ = 'factory' AND TEXT_ = 'NBU' THEN '✅ factory=NBU'
        WHEN NAME_ = 'lineName' AND TEXT_ = 'E5' THEN '✅ lineName=E5'
        ELSE '❓ 其他組合'
    END AS mapping_status
FROM bronze.bpm_act_hi_varinst 
WHERE TEXT_ IN ('WJ2','NBU','E5','CNE')
GROUP BY NAME_, TEXT_
ORDER BY NAME_, TEXT_;

-- ========================================
-- B. 用 MDM 查出同樣語意的維度結果（新邏輯）
-- ========================================
-- 使用 MDM 表串接，驗證能否得到相同的維度組合

SELECT 'B. MDM 新邏輯驗證' AS validation_type;

WITH mdm_mapping AS (
    SELECT 
        l.LINE_NAME,
        l.LINE_DESC,
        l.PROD_AREA_ID,
        
        -- Factory 維度
        p.FACTORY as factory_code,
        p.PROD_AREA_DESC as factory_name,
        
        -- Plant 維度
        mp.MFG_PLANT_CODE as plant_code,
        mp.MFG_PLANT_DESC as plant_name,
        
        -- Region 維度
        fa.MFG_SITE as region_code,
        ms.MFG_SITE_DESC as region_name,
        
        -- 驗證標記
        CASE 
            WHEN fa.MFG_SITE = 'CNE' THEN '✅ region=CNE'
            ELSE '❌ region≠CNE'
        END AS region_check,
        
        CASE 
            WHEN mp.MFG_PLANT_CODE = 'WJ2' THEN '✅ plant=WJ2'
            ELSE '❌ plant≠WJ2'
        END AS plant_check,
        
        CASE 
            WHEN p.FACTORY = 'NBU' THEN '✅ factory=NBU'
            ELSE '❌ factory≠NBU'
        END AS factory_check,
        
        CASE 
            WHEN l.LINE_NAME = 'E5' THEN '✅ lineName=E5'
            ELSE '❌ lineName≠E5'
        END AS line_check
        
    FROM bronze.common_mdm_line_desc_master l
    LEFT JOIN bronze.common_mdm_prod_area_master p 
        ON l.PROD_AREA_ID = p.PROD_AREA_ID
    LEFT JOIN bronze.common_mdm_mfg_plant_master mp 
        ON p.FACTORY = mp.FACTORY AND mp.VALIDITY = 'Y'
    LEFT JOIN bronze.common_mdm_factory_area_master fa 
        ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
    LEFT JOIN bronze.common_mdm_mfg_site_master ms 
        ON fa.MFG_SITE = ms.MFG_SITE
    WHERE l.VALID_FLAG = 'Y'
      AND (l.LINE_NAME = 'E5' OR p.FACTORY = 'NBU' OR mp.MFG_PLANT_CODE = 'WJ2' OR fa.MFG_SITE = 'CNE')
)

SELECT 
    region_code,
    region_name,
    plant_code,
    plant_name,
    factory_code,
    factory_name,
    LINE_NAME,
    LINE_DESC,
    region_check,
    plant_check,
    factory_check,
    line_check,
    
    -- 完整匹配檢查
    CASE 
        WHEN region_code = 'CNE' AND plant_code = 'WJ2' AND factory_code = 'NBU' AND LINE_NAME = 'E5'
        THEN '🎉 完全匹配 CNE-WJ2-NBU-E5'
        ELSE '❌ 部分匹配'
    END AS full_match_status
    
FROM mdm_mapping
ORDER BY region_code, plant_code, factory_code, LINE_NAME;

-- ========================================
-- C. 對照驗證（VARINST vs MDM）
-- ========================================
-- 將 varinst 和 MDM 的結果進行對照

SELECT 'C. VARINST vs MDM 對照驗證' AS validation_type;

WITH varinst_pivoted AS (
    SELECT 
        PROC_INST_ID_,
        MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS varinst_region,
        MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS varinst_plant,
        MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS varinst_factory,
        MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS varinst_lineName
    FROM bronze.bpm_act_hi_varinst
    WHERE TEXT_ IN ('WJ2','NBU','E5','CNE')
    GROUP BY PROC_INST_ID_
    HAVING varinst_region = 'CNE' OR varinst_plant = 'WJ2' OR varinst_factory = 'NBU' OR varinst_lineName = 'E5'
),

mdm_lookup AS (
    SELECT 
        l.LINE_NAME,
        p.FACTORY as factory_code,
        mp.MFG_PLANT_CODE as plant_code,
        fa.MFG_SITE as region_code
    FROM bronze.common_mdm_line_desc_master l
    LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
    LEFT JOIN bronze.common_mdm_mfg_plant_master mp ON p.FACTORY = mp.FACTORY AND mp.VALIDITY = 'Y'
    LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
    WHERE l.VALID_FLAG = 'Y'
)

SELECT 
    -- VARINST 來源
    v.varinst_region,
    v.varinst_plant,
    v.varinst_factory,
    v.varinst_lineName,
    
    -- MDM 對應結果
    m.region_code AS mdm_region,
    m.plant_code AS mdm_plant,
    m.factory_code AS mdm_factory,
    m.LINE_NAME AS mdm_lineName,
    
    -- 一致性檢查
    CASE WHEN v.varinst_region = m.region_code THEN '✅' ELSE '❌' END AS region_match,
    CASE WHEN v.varinst_plant = m.plant_code THEN '✅' ELSE '❌' END AS plant_match,
    CASE WHEN v.varinst_factory = m.factory_code THEN '✅' ELSE '❌' END AS factory_match,
    CASE WHEN v.varinst_lineName = m.LINE_NAME THEN '✅' ELSE '❌' END AS line_match,
    
    count() AS occurrence_count
    
FROM varinst_pivoted v
LEFT JOIN mdm_lookup m ON v.varinst_lineName = m.LINE_NAME
GROUP BY 
    v.varinst_region, v.varinst_plant, v.varinst_factory, v.varinst_lineName,
    m.region_code, m.plant_code, m.factory_code, m.LINE_NAME
ORDER BY occurrence_count DESC
LIMIT 20;

-- ========================================
-- D. 成功條件驗證
-- ========================================
-- 驗證是否滿足 Definition of Done

SELECT 'D. Definition of Done 驗證' AS validation_type;

WITH success_criteria AS (
    SELECT 
        l.LINE_NAME,
        p.FACTORY as factory_code,
        mp.MFG_PLANT_CODE as plant_code,
        fa.MFG_SITE as region_code,
        
        -- 檢查各維度是否出現在正確位置
        CASE WHEN mp.MFG_PLANT_CODE = 'WJ2' THEN 1 ELSE 0 END AS wj2_in_plant,
        CASE WHEN p.FACTORY = 'NBU' THEN 1 ELSE 0 END AS nbu_in_factory,
        CASE WHEN l.LINE_NAME = 'E5' THEN 1 ELSE 0 END AS e5_in_line,
        CASE WHEN fa.MFG_SITE = 'CNE' THEN 1 ELSE 0 END AS cne_in_region
        
    FROM bronze.common_mdm_line_desc_master l
    LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
    LEFT JOIN bronze.common_mdm_mfg_plant_master mp ON p.FACTORY = mp.FACTORY AND mp.VALIDITY = 'Y'
    LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
    WHERE l.VALID_FLAG = 'Y'
      AND (l.LINE_NAME = 'E5' OR p.FACTORY = 'NBU' OR mp.MFG_PLANT_CODE = 'WJ2' OR fa.MFG_SITE = 'CNE')
)

SELECT 
    'WJ2 出現在 plant 欄位' AS criteria,
    sum(wj2_in_plant) AS success_count,
    CASE WHEN sum(wj2_in_plant) > 0 THEN '✅ PASS' ELSE '❌ FAIL' END AS status
FROM success_criteria

UNION ALL

SELECT 
    'NBU 出現在 factory 欄位' AS criteria,
    sum(nbu_in_factory) AS success_count,
    CASE WHEN sum(nbu_in_factory) > 0 THEN '✅ PASS' ELSE '❌ FAIL' END AS status
FROM success_criteria

UNION ALL

SELECT 
    'E5 出現在 lineName 欄位' AS criteria,
    sum(e5_in_line) AS success_count,
    CASE WHEN sum(e5_in_line) > 0 THEN '✅ PASS' ELSE '❌ FAIL' END AS status
FROM success_criteria

UNION ALL

SELECT 
    'CNE 出現在 region 欄位' AS criteria,
    sum(cne_in_region) AS success_count,
    CASE WHEN sum(cne_in_region) > 0 THEN '✅ PASS' ELSE '❌ FAIL' END AS status
FROM success_criteria;

-- ========================================
-- E. 完整組合驗證
-- ========================================
-- 檢查是否存在完整的 CNE-WJ2-NBU-E5 組合

SELECT 'E. 完整組合存在性驗證' AS validation_type;

SELECT 
    region_code,
    plant_code,
    factory_code,
    LINE_NAME,
    '🎉 找到完整的 CNE-WJ2-NBU-E5 組合' AS result_status
FROM (
    SELECT 
        fa.MFG_SITE as region_code,
        mp.MFG_PLANT_CODE as plant_code,
        p.FACTORY as factory_code,
        l.LINE_NAME
    FROM bronze.common_mdm_line_desc_master l
    LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
    LEFT JOIN bronze.common_mdm_mfg_plant_master mp ON p.FACTORY = mp.FACTORY AND mp.VALIDITY = 'Y'
    LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
    WHERE l.VALID_FLAG = 'Y'
      AND fa.MFG_SITE = 'CNE'
      AND mp.MFG_PLANT_CODE = 'WJ2'
      AND p.FACTORY = 'NBU'
      AND l.LINE_NAME = 'E5'
)

UNION ALL

SELECT 
    'N/A' AS region_code,
    'N/A' AS plant_code,
    'N/A' AS factory_code,
    'N/A' AS LINE_NAME,
    '❌ 未找到完整的 CNE-WJ2-NBU-E5 組合' AS result_status
WHERE NOT EXISTS (
    SELECT 1
    FROM bronze.common_mdm_line_desc_master l
    LEFT JOIN bronze.common_mdm_prod_area_master p ON l.PROD_AREA_ID = p.PROD_AREA_ID
    LEFT JOIN bronze.common_mdm_mfg_plant_master mp ON p.FACTORY = mp.FACTORY AND mp.VALIDITY = 'Y'
    LEFT JOIN bronze.common_mdm_factory_area_master fa ON p.FACTORY = fa.FACTORY AND fa.VALID = '1'
    WHERE l.VALID_FLAG = 'Y'
      AND fa.MFG_SITE = 'CNE'
      AND mp.MFG_PLANT_CODE = 'WJ2'
      AND p.FACTORY = 'NBU'
      AND l.LINE_NAME = 'E5'
);