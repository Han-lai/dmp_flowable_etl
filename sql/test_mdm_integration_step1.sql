-- ========================================
-- 測試 MDM 整合 - 第一步：建立基礎 MVIEW
-- ========================================

-- 先檢查 silver.dim_mfg_five_level 是否存在
SELECT 'Checking silver.dim_mfg_five_level...' AS status;
SELECT COUNT(*) as record_count FROM silver.dim_mfg_five_level;

-- 建立簡化版 MDM 整合 MVIEW
DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution_mdm_test;

CREATE MATERIALIZED VIEW silver.mv_fact_task_vx_attribution_mdm_test
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (task_id)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT
    -- 主鍵
    t.ID_ AS task_id,
    
    -- 時間維度
    COALESCE(toDate(t.START_TIME_), toDate('1970-01-01')) AS task_create_date,
    t.START_TIME_ AS task_create_time,
    t.END_TIME_ AS task_end_time,
    
    -- 任務屬性
    COALESCE(
        CASE 
            WHEN t.END_TIME_ IS NOT NULL THEN 'DONE'
            WHEN t.ASSIGNEE_ IS NOT NULL AND t.ASSIGNEE_ != '' THEN 'DOING' 
            ELSE 'TODO'
        END, 
        'Unknown'
    ) AS task_status,
    
    t.TASK_DEF_KEY_ AS task_definition_key,
    
    -- Vx 歸屬邏輯
    CASE 
        WHEN COALESCE(v.varinst_moNumber, '') LIKE '315%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '196%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
        THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
        WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
        ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
    END AS vx_type,
    
    -- ========================================
    -- 製造五階維度（MDM 整合版本）
    -- ========================================
    
    -- Region 層級（MDM 主來源）
    COALESCE(mdm.region_code, '') AS region_code,
    COALESCE(mdm.region_name, '') AS region_name,
    
    -- Plant 層級（MDM 主來源，Flowable 輔助）
    COALESCE(
        mdm.plant_code,         -- MDM 主來源
        v.varinst_plant,        -- Flowable 輔助來源
        ''
    ) AS plant_code,
    COALESCE(mdm.plant_name, '') AS plant_name,
    
    -- Factory 層級（MDM 主來源，Flowable 輔助）
    COALESCE(
        mdm.factory_code,       -- MDM 主來源
        v.varinst_factory,      -- Flowable 輔助來源
        ''
    ) AS factory_code,
    COALESCE(mdm.factory_name, '') AS factory_name,
    
    -- Line 層級（MDM 主來源，Flowable 輔助）
    COALESCE(
        mdm.line_name,          -- MDM 主來源
        v.varinst_lineName,     -- Flowable 輔助來源
        ''
    ) AS line_code,
    COALESCE(mdm.line_desc, '') AS line_name,
    
    -- 維度資料來源標記
    CASE 
        WHEN mdm.line_name IS NOT NULL THEN 'MDM_PRIMARY'
        WHEN v.varinst_lineName IS NOT NULL THEN 'FLOWABLE_FALLBACK'
        ELSE 'NO_DIMENSION'
    END AS dimension_source,
    
    -- 維度資料品質標記
    COALESCE(mdm.is_valid, 0) AS dimension_is_valid,
    
    -- ========================================
    -- 相容性維度欄位（保持向後相容）
    -- ========================================
    COALESCE(
        mdm.plant_code,
        v.varinst_plant,
        ''
    ) AS plant,  -- 相容性欄位
    
    COALESCE(
        mdm.factory_code,
        v.varinst_factory,
        ''
    ) AS factory,  -- 相容性欄位
    
    COALESCE(
        mdm.line_name,
        v.varinst_lineName,
        ''
    ) AS line,  -- 相容性欄位
    
    -- 關聯欄位
    t.PROC_INST_ID_ AS proc_inst_id,
    COALESCE(v.varinst_moNumber, '') AS mo_number,
    
    -- Metadata
    now64(3) AS _mview_update_time

FROM bronze.bmp_act_hi_taskinst t
LEFT JOIN bronze.bmp_act_hi_procinst p 
    ON t.PROC_INST_ID_ = p.PROC_INST_ID_
LEFT JOIN silver.mv_varinst_pivoted v
    ON t.PROC_INST_ID_ = v.PROC_INST_ID_
-- 透過 Line Name 串接 MDM 五階維度表
LEFT JOIN silver.dim_mfg_five_level mdm 
    ON COALESCE(v.varinst_lineName, '') = mdm.line_name
WHERE t.ID_ IS NOT NULL 
  AND t.ID_ != ''
LIMIT 100000;  -- 限制記錄數進行測試

-- 檢查建立結果
SELECT 'MDM Integration Test MVIEW Created' AS status,
       COUNT(*) AS record_count
FROM silver.mv_fact_task_vx_attribution_mdm_test;