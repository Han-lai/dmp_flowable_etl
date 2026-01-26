-- ========================================
-- 維度補齊邏輯實作 SQL
-- ========================================
-- 規則：VARINST 有資料就用 VARINST，VARINST 沒資料才用 MDM 補齊
-- 用於 Silver 層 MVIEW 實作

-- 範例：在 silver.mv_fact_task_vx_attribution_mdm 中的實作邏輯

CREATE OR REPLACE VIEW silver.vw_dimension_backfill_demo AS
WITH varinst_pivoted AS (
    SELECT 
        PROC_INST_ID_,
        
        -- 從 VARINST 取得維度值
        MAX(CASE WHEN NAME_ = 'region' AND TEXT_ IS NOT NULL AND TEXT_ != '' THEN TEXT_ END) AS varinst_region,
        MAX(CASE WHEN NAME_ = 'plant' AND TEXT_ IS NOT NULL AND TEXT_ != '' THEN TEXT_ END) AS varinst_plant,
        MAX(CASE WHEN NAME_ = 'factory' AND TEXT_ IS NOT NULL AND TEXT_ != '' THEN TEXT_ END) AS varinst_factory,
        MAX(CASE WHEN NAME_ = 'lineName' AND TEXT_ IS NOT NULL AND TEXT_ != '' THEN TEXT_ END) AS varinst_line
        
    FROM bronze.bpm_act_hi_varinst
    WHERE NAME_ IN ('region', 'plant', 'factory', 'lineName')
    GROUP BY PROC_INST_ID_
),

mdm_enriched AS (
    SELECT 
        v.*,
        
        -- 從 MDM 取得補齊維度值 (透過 lineName join)
        mdm.region_code AS mdm_region,
        mdm.plant_code AS mdm_plant,
        mdm.factory_code AS mdm_factory,
        mdm.line_name AS mdm_line
        
    FROM varinst_pivoted AS v
    LEFT JOIN silver.dim_mfg_five_level AS mdm ON v.varinst_line = mdm.line_name
)

SELECT 
    PROC_INST_ID_,
    
    -- 實作補齊邏輯：VARINST 優先，MDM 補齊缺失
    COALESCE(varinst_region, mdm_region, '') AS region,
    COALESCE(varinst_plant, mdm_plant, '') AS plant,
    COALESCE(varinst_factory, mdm_factory, '') AS factory,
    COALESCE(varinst_line, mdm_line, '') AS line_name,
    
    -- 資料來源標記
    CASE 
        WHEN varinst_region IS NOT NULL THEN 'VARINST'
        WHEN mdm_region IS NOT NULL THEN 'MDM'
        ELSE 'MISSING'
    END AS region_source,
    
    CASE 
        WHEN varinst_plant IS NOT NULL THEN 'VARINST'
        WHEN mdm_plant IS NOT NULL THEN 'MDM'
        ELSE 'MISSING'
    END AS plant_source,
    
    CASE 
        WHEN varinst_factory IS NOT NULL THEN 'VARINST'
        WHEN mdm_factory IS NOT NULL THEN 'MDM'
        ELSE 'MISSING'
    END AS factory_source,
    
    CASE 
        WHEN varinst_line IS NOT NULL THEN 'VARINST'
        WHEN mdm_line IS NOT NULL THEN 'MDM'
        ELSE 'MISSING'
    END AS line_source,
    
    -- 整體資料來源標記
    CASE 
        WHEN varinst_region IS NOT NULL OR varinst_plant IS NOT NULL 
             OR varinst_factory IS NOT NULL OR varinst_line IS NOT NULL 
        THEN 
            CASE 
                WHEN mdm_region IS NOT NULL OR mdm_plant IS NOT NULL 
                     OR mdm_factory IS NOT NULL OR mdm_line IS NOT NULL 
                THEN 'VARINST_MDM_HYBRID'
                ELSE 'VARINST_ONLY'
            END
        WHEN mdm_region IS NOT NULL OR mdm_plant IS NOT NULL 
             OR mdm_factory IS NOT NULL OR mdm_line IS NOT NULL 
        THEN 'MDM_ONLY'
        ELSE 'NO_DIMENSION'
    END AS overall_source
    
FROM mdm_enriched;