-- ========================================
-- 初始化: 五階製造維度主檔 (silver.mv_dim_mfg_five_level)
-- 正確路徑: line_desc → prod_area → factory_area → mfg_site
-- 前置: bronze.common_mdm_* 系列表必須已透過 sync_unified_odbc.py 同步過資料
--       (不是只要表存在，是要有實際資料，否則本語句會 INSERT 0 筆)
-- 執行時機: Bronze 同步完成後、Silver/Gold 運算開始前 (init_pipeline.sh Phase 2.5)
-- 冪等性: 先 TRUNCATE 再 INSERT，避免重跑時因 ReplacingMergeTree 尚未背景合併
--         導致重複列，讓下游 backfill_silver.sql 的 JOIN（未加 FINAL）產生 fan-out。
-- ========================================

TRUNCATE TABLE IF EXISTS silver.mv_dim_mfg_five_level;

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
