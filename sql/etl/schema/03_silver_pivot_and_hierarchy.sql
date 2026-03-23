-- ========================================
-- 步驟 3: Silver Layer - Pivot & Hierarchy
-- 內容: VarInst Pivot, Five Level Dimension
-- 前置: 01_bronze_flowable_core, 02_bronze_common_dims
-- ========================================

-- ========================================
-- 2.1 VARINST 透視表
-- ========================================
-- ========================================
-- 2.1 VARINST 透視表 (改為實體表以支援 Batch 寫入)
-- ========================================

-- DROP TABLE IF EXISTS silver.mv_varinst_pivoted;

CREATE TABLE silver.mv_varinst_pivoted (
    PROC_INST_ID_ String,
    varinst_region String,
    varinst_plant String,
    varinst_factory String,
    varinst_lineName String,
    varinst_moNumber String,
    varinst_autoComplete String,
    _refresh_time DateTime64(3)
)
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (PROC_INST_ID_)
TTL toDate(_refresh_time) + INTERVAL 1 YEAR
SETTINGS allow_nullable_key = 1;

-- 驗證
SELECT 'mv_varinst_pivoted' AS table_name, count() AS row_count 
FROM silver.mv_varinst_pivoted;

-- ========================================
-- 2.2 五階維度主檔 (修正 JOIN 邏輯)
-- 正確路徑: line_desc → prod_area → factory_area → mfg_site
-- ========================================
-- DROP TABLE IF EXISTS silver.mv_dim_mfg_five_level;

CREATE TABLE silver.mv_dim_mfg_five_level (
    line_name String,
    line_desc String,
    prod_area_code String,
    factory_code String,
    factory_name String,
    plant_code String,
    plant_name String,
    region_code String,
    region_name String,
    _mview_update_time DateTime64(3)
)
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (plant_code, line_name)
SETTINGS allow_nullable_key = 1;

-- 首次建立時，手動從來源生成資料
INSERT INTO silver.mv_dim_mfg_five_level
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
