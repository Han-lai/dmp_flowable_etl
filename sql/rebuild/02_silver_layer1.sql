-- ========================================
-- 步驟 2-3: Silver Layer 1 - VARINST 透視 + 五階維度
-- 執行時間: 約 2-3 分鐘
-- 注意: 需要先執行完畢再執行 03_silver_layer2.sql
-- ========================================

-- ========================================
-- 2.1 VARINST 透視表
-- ========================================
DROP TABLE IF EXISTS silver.mv_varinst_pivoted;

CREATE MATERIALIZED VIEW silver.mv_varinst_pivoted
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (PROC_INST_ID_)
TTL toDate(_mview_update_time) + INTERVAL 1 YEAR
SETTINGS allow_nullable_key = 1
POPULATE AS
SELECT
    PROC_INST_ID_,
    argMaxIf(TEXT_, REV_, NAME_ = 'region') AS varinst_region,
    argMaxIf(TEXT_, REV_, NAME_ = 'plant') AS varinst_plant,
    argMaxIf(TEXT_, REV_, NAME_ = 'factory') AS varinst_factory,
    argMaxIf(TEXT_, REV_, NAME_ = 'lineName') AS varinst_lineName,
    argMaxIf(TEXT_, REV_, NAME_ = 'moNumber') AS varinst_moNumber,
    now64(3) AS _mview_update_time
FROM bronze.bpm_act_hi_varinst
WHERE PROC_INST_ID_ IS NOT NULL AND PROC_INST_ID_ != ''
  AND NAME_ IN ('region', 'plant', 'factory', 'lineName', 'moNumber')
GROUP BY PROC_INST_ID_;

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
ORDER BY (line_name)
SETTINGS allow_nullable_key = 1
POPULATE AS
SELECT DISTINCT
    ld.LINE_NAME AS line_name,
    ld.LINE_DESC AS line_desc,
    pa.PROD_AREA_CODE AS prod_area_code,
    fa.FACTORY AS factory_code,
    fa.FACTORY_DESC AS factory_name,
    fa.PLANT_NODE AS plant_code,
    fa.PLANT_NODE_DESC AS plant_name,
    fa.REGION AS region_code,
    sm.MFG_SITE_DESC AS region_name,
    now64(3) AS _mview_update_time
FROM bronze.common_mdm_line_desc_master ld
LEFT JOIN bronze.common_mdm_prod_area_master pa ON ld.PROD_AREA_ID = pa.PROD_AREA_ID
LEFT JOIN bronze.common_mdm_factory_area_master fa ON pa.FACTORY = fa.FACTORY
LEFT JOIN bronze.common_mdm_mfg_site_master sm ON fa.MFG_SITE = sm.MFG_SITE
WHERE ld.LINE_NAME IS NOT NULL AND ld.LINE_NAME != '';

-- 驗證
SELECT 'mv_dim_mfg_five_level' AS table_name, count() AS row_count 
FROM silver.mv_dim_mfg_five_level;

SELECT 'Silver Layer 1 完成' AS status;
