-- ========================================
-- 步驟 3: Silver Layer - Pivot & Hierarchy
-- 內容: VarInst Pivot, Five Level Dimension
-- 前置: 01_bronze_flowable_core, 02_bronze_common_dims
-- ========================================

-- ========================================
-- 2.1 VARINST 透視表
-- ========================================
-- 啟用 REFRESHABLE MView 實驗功能
SET allow_experimental_refreshable_materialized_view = 1;

-- DROP TABLE IF EXISTS silver.mv_varinst_pivoted;

CREATE MATERIALIZED VIEW silver.mv_varinst_pivoted
REFRESH EVERY 1 DAY OFFSET 2 HOUR
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (PROC_INST_ID_)
TTL toDate(_refresh_time) + INTERVAL 1 YEAR
SETTINGS allow_nullable_key = 1
AS
SELECT
    PROC_INST_ID_,
    argMaxIf(TEXT_, REV_, NAME_ = 'region') AS varinst_region,
    argMaxIf(TEXT_, REV_, NAME_ = 'plant') AS varinst_plant,
    argMaxIf(TEXT_, REV_, NAME_ = 'factory') AS varinst_factory,
    argMaxIf(TEXT_, REV_, NAME_ = 'lineName') AS varinst_lineName,
    argMaxIf(TEXT_, REV_, NAME_ = 'moNumber') AS varinst_moNumber,
    now() AS _refresh_time
FROM bronze.bpm_act_hi_varinst
WHERE PROC_INST_ID_ IS NOT NULL AND PROC_INST_ID_ != ''
  AND NAME_ IN ('region', 'plant', 'factory', 'lineName', 'moNumber')
GROUP BY PROC_INST_ID_;

-- 手動觸發首次刷新
SYSTEM REFRESH VIEW silver.mv_varinst_pivoted;


-- 驗證
SELECT 'mv_varinst_pivoted' AS table_name, count() AS row_count 
FROM silver.mv_varinst_pivoted;

-- ========================================
-- 2.2 五階維度主檔 (修正 JOIN 邏輯)
-- 正確路徑: line_desc → prod_area → factory_area → mfg_site
-- ========================================
DROP TABLE IF EXISTS silver.mv_dim_mfg_five_level;

CREATE MATERIALIZED VIEW silver.mv_dim_mfg_five_level
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (plant_code, line_name)
SETTINGS allow_nullable_key = 1
POPULATE AS
SELECT DISTINCT
    ld.LINE_NAME AS line_name,
    ld.LINE_DESC AS line_desc,
    pa.PROD_AREA_CODE AS prod_area_code,
    -- Factory Level (User Request: Use PM.MFG_PLANT_CODE)
    pm.MFG_PLANT_CODE AS factory_code,
    pm.MFG_PLANT_DESC AS factory_name,
    -- Plant Level (User Request: Use PM.FACTORY)
    pm.FACTORY AS plant_code,
    pm.FACTORY AS plant_name, -- Use Code as Name since no desc available in PM
    -- Region Level (Use MFG_SITE as region_code per user request 2026-02-04)
    fa.MFG_SITE AS region_code,
    sm.MFG_SITE_DESC AS region_name,
    now() AS _mview_update_time
FROM bronze.common_mdm_line_desc_master ld
LEFT JOIN bronze.common_mdm_prod_area_master pa ON ld.PROD_AREA_ID = pa.PROD_AREA_ID
-- FIX: Join to mfg_plant_master for correct Plant/Factory info (2026-02-03)
LEFT JOIN bronze.common_mdm_mfg_plant_master pm ON pa.MFG_PLANT_ID = pm.MFG_PLANT_ID
-- Keep FA join for Region info
LEFT JOIN bronze.common_mdm_factory_area_master fa ON pa.FACTORY = fa.FACTORY
LEFT JOIN bronze.common_mdm_mfg_site_master sm ON fa.MFG_SITE = sm.MFG_SITE
WHERE ld.LINE_NAME IS NOT NULL AND ld.LINE_NAME != '';

-- 驗證
SELECT 'mv_dim_mfg_five_level' AS table_name, count() AS row_count 
FROM silver.mv_dim_mfg_five_level;

SELECT 'Silver Layer 1 完成' AS status;
