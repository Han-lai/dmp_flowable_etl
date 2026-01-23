-- 建立修正後的 MDM 整合 MVIEW
DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution_mdm;

CREATE MATERIALIZED VIEW silver.mv_fact_task_vx_attribution_mdm
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (task_id)
SETTINGS allow_nullable_key = 1
POPULATE
AS
WITH 
-- 建立維度對應邏輯
dimension_mapping AS (
    SELECT 
        t.ID_ AS task_id,
        t.PROC_INST_ID_ AS proc_inst_id,
        
        -- 從 Flowable 變數取得原始維度值
        v.varinst_plant AS flowable_plant,
        v.varinst_factory AS flowable_factory,
        v.varinst_lineName AS flowable_line,
        
        -- 從 Business Key 解析維度資訊（備用）
        CASE 
            WHEN p.BUSINESS_KEY_ LIKE '%"plant":"%' THEN 
                extract(p.BUSINESS_KEY_, '"plant":"([^"]+)"')
            ELSE ''
        END AS business_key_plant,
        
        -- 透過 Line 串接 MDM 維度（主要來源）
        mdm.region_code AS mdm_region,
        mdm.plant_code AS mdm_plant,
        mdm.factory_code AS mdm_factory,
        mdm.line_name AS mdm_line,
        mdm.region_name AS mdm_region_name,
        mdm.plant_name AS mdm_plant_name,
        mdm.factory_name AS mdm_factory_name,
        mdm.line_desc AS mdm_line_desc,
        mdm.is_valid AS mdm_is_valid,
        mdm.data_source AS mdm_data_source
        
    FROM bronze.bpm_act_hi_taskinst t
    LEFT JOIN bronze.bpm_act_hi_procinst p ON t.PROC_INST_ID_ = p.PROC_INST_ID_
    LEFT JOIN silver.mv_varinst_pivoted v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
    -- 透過 Line Name 串接 MDM 五階維度表
    LEFT JOIN silver.dim_mfg_five_level mdm ON COALESCE(v.varinst_lineName, '') = mdm.line_name
    WHERE t.ID_ IS NOT NULL AND t.ID_ != ''
)

SELECT
    -- 主鍵
    t.ID_ AS task_id,
    
    -- 時間維度
    COALESCE(toDate(t.START_TIME_), toDate('1970-01-01')) AS task_create_date,
    toDateOrNull(t.END_TIME_) AS task_end_date,
    t.START_TIME_ AS task_create_time,
    t.CLAIM_TIME_ AS task_claim_time,
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
    
    COALESCE(
        CASE WHEN tb.LONG_ = 1 THEN 'Y' ELSE 'N' END, 
        'N'
    ) AS task_bypass,
    
    t.TASK_DEF_KEY_ AS task_definition_key,
    t.NAME_ AS task_name,
    
    -- 人員資訊
    he.EmpName AS task_assignee_name,
    t.ASSIGNEE_ AS task_assignee_account,
    
    -- 預計算：Vx 歸屬（修正後的邏輯：工單號規則優先級最高）
    CASE 
        -- 優先級 1：工單號規則（最高，覆蓋所有 TaskDefinitionKey）
        WHEN COALESCE(v.varinst_moNumber, '') LIKE '196%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '315%'
        THEN 'V1'
        
        -- 優先級 2：TaskDefinitionKey 前綴（當工單號規則不符合時）
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
        WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
        
        -- 預設值
        ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
    END AS vx_type,
    
    -- Plant 層級（修正：優先使用 MDM，Flowable factory 作為 Plant 輔助來源）
    COALESCE(
        dm.mdm_plant,           -- MDM 主來源
        dm.flowable_factory,    -- Flowable factory 變數實際對應 Plant 層級
        dm.business_key_plant,  -- Business Key 備用來源
        ''
    ) AS plant_code,
    COALESCE(dm.mdm_plant_name, '') AS plant_name,
    
    -- Factory 層級（修正：優先使用 MDM，Flowable plant 作為 Factory 輔助來源）
    COALESCE(
        dm.mdm_factory,         -- MDM 主來源
        dm.flowable_plant,      -- Flowable plant 變數實際對應 Factory 層級
        ''
    ) AS factory_code,
    COALESCE(dm.mdm_factory_name, '') AS factory_name,
    
    -- 相容性維度欄位（修正對應關係）
    COALESCE(
        dm.mdm_plant,
        dm.flowable_factory,    -- Flowable factory 變數實際對應 Plant 層級
        dm.business_key_plant,
        ''
    ) AS plant,  -- 相容性欄位
    
    COALESCE(
        dm.mdm_factory,
        dm.flowable_plant,      -- Flowable plant 變數實際對應 Factory 層級
        ''
    ) AS factory,  -- 相容性欄位
    
    -- Metadata
    now64(3) AS _mview_update_time

FROM bronze.bpm_act_hi_taskinst t
LEFT JOIN bronze.bpm_act_hi_procinst p 
    ON t.PROC_INST_ID_ = p.PROC_INST_ID_
LEFT JOIN silver.mv_varinst_pivoted v
    ON t.PROC_INST_ID_ = v.PROC_INST_ID_
LEFT JOIN bronze.common_hr_employee he
    ON t.ASSIGNEE_ = he.EmpCode
-- TaskBypass 來自任務層級變數 autoComplete
LEFT JOIN bronze.bpm_act_hi_varinst tb
    ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
-- 維度對應邏輯
LEFT JOIN dimension_mapping dm
    ON t.ID_ = dm.task_id
WHERE t.ID_ IS NOT NULL 
  AND t.ID_ != '';