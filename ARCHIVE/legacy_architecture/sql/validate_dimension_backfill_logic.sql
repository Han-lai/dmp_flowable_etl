-- ========================================
-- 維度補齊邏輯驗證 SQL
-- ========================================
-- 規則：VARINST 有資料就用 VARINST，VARINST 沒資料才用 MDM 補齊
-- 目標：產出驗收表，證明補齊邏輯正確

-- 使用非 V1 流程樣本 + 一些 V1 流程作為對照
WITH target_samples AS (
    SELECT arrayJoin([
        -- 非 V1 流程 (region 缺失，需要 MDM 補齊)
        '3c40f619-c593-11f0-8d58-1e564a6128f7',
        '38cfc17e-ef5a-11f0-a787-0a5a5063cfa7', 
        '3ca530c5-d938-11f0-8eb2-761d901080ab',
        '505b457d-63b3-11f0-b8b8-b6733f7db4dd',
        '3c60482b-ecf9-11f0-ba59-92564f99f227',
        '3ca93700-ef50-11f0-a787-0a5a5063cfa7'
    ]) AS proc_inst_id
),

-- 1. 取得 VARINST 維度值
varinst_dimensions AS (
    SELECT 
        t.proc_inst_id,
        v_region.TEXT_ AS varinst_region,
        v_plant.TEXT_ AS varinst_plant,
        v_factory.TEXT_ AS varinst_factory,
        v_line.TEXT_ AS varinst_line
         
    FROM target_samples AS t
    LEFT JOIN (
        SELECT PROC_INST_ID_, TEXT_ 
        FROM bronze.bpm_act_hi_varinst 
        WHERE NAME_ = 'region' AND TEXT_ IS NOT NULL AND TEXT_ != ''
    ) AS v_region ON t.proc_inst_id = v_region.PROC_INST_ID_
    LEFT JOIN (
        SELECT PROC_INST_ID_, TEXT_ 
        FROM bronze.bpm_act_hi_varinst 
        WHERE NAME_ = 'plant' AND TEXT_ IS NOT NULL AND TEXT_ != ''
    ) AS v_plant ON t.proc_inst_id = v_plant.PROC_INST_ID_
    LEFT JOIN (
        SELECT PROC_INST_ID_, TEXT_ 
        FROM bronze.bpm_act_hi_varinst 
        WHERE NAME_ = 'factory' AND TEXT_ IS NOT NULL AND TEXT_ != ''
    ) AS v_factory ON t.proc_inst_id = v_factory.PROC_INST_ID_
    LEFT JOIN (
        SELECT PROC_INST_ID_, TEXT_ 
        FROM bronze.bpm_act_hi_varinst 
        WHERE NAME_ = 'lineName' AND TEXT_ IS NOT NULL AND TEXT_ != ''
    ) AS v_line ON t.proc_inst_id = v_line.PROC_INST_ID_
),

-- 2. 取得 MDM 維度值 (透過 lineName join)
mdm_dimensions AS (
    SELECT 
        v.proc_inst_id,
        
        -- 使用 lineName 直接 join MDM
        mdm.region_code AS mdm_region,
        mdm.plant_code AS mdm_plant,
        mdm.factory_code AS mdm_factory,
        mdm.line_name AS mdm_line
        
    FROM varinst_dimensions AS v
    LEFT JOIN silver.dim_mfg_five_level AS mdm ON v.varinst_line = mdm.line_name
),

-- 3. 實作補齊邏輯：VARINST 優先，MDM 補齊
dimension_backfill AS (
    SELECT 
        v.proc_inst_id,
        
        -- VARINST 原始值
        v.varinst_region,
        v.varinst_plant,
        v.varinst_factory,
        v.varinst_line,
        
        -- MDM 補齊值
        m.mdm_region,
        m.mdm_plant,
        m.mdm_factory,
        m.mdm_line,
        
        -- 最終值：VARINST 優先，缺失時用 MDM 補齊
        COALESCE(v.varinst_region, m.mdm_region) AS final_region,
        COALESCE(v.varinst_plant, m.mdm_plant) AS final_plant,
        COALESCE(v.varinst_factory, m.mdm_factory) AS final_factory,
        COALESCE(v.varinst_line, m.mdm_line) AS final_line,
        
        -- 資料來源標記
        CASE 
            WHEN v.varinst_region IS NOT NULL THEN 'VARINST'
            WHEN m.mdm_region IS NOT NULL THEN 'MDM'
            ELSE 'MISSING'
        END AS region_source,
        
        CASE 
            WHEN v.varinst_plant IS NOT NULL THEN 'VARINST'
            WHEN m.mdm_plant IS NOT NULL THEN 'MDM'
            ELSE 'MISSING'
        END AS plant_source,
        
        CASE 
            WHEN v.varinst_factory IS NOT NULL THEN 'VARINST'
            WHEN m.mdm_factory IS NOT NULL THEN 'MDM'
            ELSE 'MISSING'
        END AS factory_source,
        
        CASE 
            WHEN v.varinst_line IS NOT NULL THEN 'VARINST'
            WHEN m.mdm_line IS NOT NULL THEN 'MDM'
            ELSE 'MISSING'
        END AS line_source
        
    FROM varinst_dimensions AS v
    LEFT JOIN mdm_dimensions AS m ON v.proc_inst_id = m.proc_inst_id
)

-- 4. 產出驗收表格式
SELECT 
    proc_inst_id,
    'region' AS dimension,
    COALESCE(varinst_region, 'NULL') AS varinst_value,
    COALESCE(mdm_region, 'NULL') AS mdm_value,
    COALESCE(final_region, 'NULL') AS final_value,
    region_source AS source
FROM dimension_backfill

UNION ALL

SELECT 
    proc_inst_id,
    'plant' AS dimension,
    COALESCE(varinst_plant, 'NULL') AS varinst_value,
    COALESCE(mdm_plant, 'NULL') AS mdm_value,
    COALESCE(final_plant, 'NULL') AS final_value,
    plant_source AS source
FROM dimension_backfill

UNION ALL

SELECT 
    proc_inst_id,
    'factory' AS dimension,
    COALESCE(varinst_factory, 'NULL') AS varinst_value,
    COALESCE(mdm_factory, 'NULL') AS mdm_value,
    COALESCE(final_factory, 'NULL') AS final_value,
    factory_source AS source
FROM dimension_backfill

UNION ALL

SELECT 
    proc_inst_id,
    'lineName' AS dimension,
    COALESCE(varinst_line, 'NULL') AS varinst_value,
    COALESCE(mdm_line, 'NULL') AS mdm_value,
    COALESCE(final_line, 'NULL') AS final_value,
    line_source AS source
FROM dimension_backfill

ORDER BY proc_inst_id, dimension;