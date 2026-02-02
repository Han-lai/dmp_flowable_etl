-- ========================================
-- Silver 層 Views 和 MViews - 含維度補齊邏輯
-- 規則：VARINST 優先，MDM 補齊，並標記資料來源
-- ========================================

-- ========================================
-- 1. VARINST 變數透視表
-- ========================================

DROP TABLE IF EXISTS silver.mv_varinst_pivoted;

CREATE MATERIALIZED VIEW silver.mv_varinst_pivoted
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (PROC_INST_ID_)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT
    PROC_INST_ID_,
    
    -- 透視 VARINST 變數
    argMaxIf(TEXT_, REV_, NAME_ = 'region') AS varinst_region,
    argMaxIf(TEXT_, REV_, NAME_ = 'plant') AS varinst_plant,
    argMaxIf(TEXT_, REV_, NAME_ = 'factory') AS varinst_factory,
    argMaxIf(TEXT_, REV_, NAME_ = 'lineName') AS varinst_lineName,
    argMaxIf(TEXT_, REV_, NAME_ = 'moNumber') AS varinst_moNumber,
    
    now64(3) AS _mview_update_time

FROM bronze.bpm_act_hi_varinst
WHERE PROC_INST_ID_ IS NOT NULL 
  AND PROC_INST_ID_ != ''
  AND NAME_ IN ('region', 'plant', 'factory', 'lineName', 'moNumber')
GROUP BY PROC_INST_ID_;

-- ========================================
-- 2. MDM 五階維度主檔
-- ========================================

DROP TABLE IF EXISTS silver.dim_mfg_five_level;

CREATE MATERIALIZED VIEW silver.dim_mfg_five_level
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (line_name)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT DISTINCT
    -- Line 層級（主鍵）
    ld.LINE_NAME AS line_name,
    ld.LINE_DESC AS line_desc,
    
    -- Factory 層級
    fa.FACTORY AS factory_code,
    fa.FACTORY_DESC AS factory_name,
    
    -- Plant 層級  
    pm.PLANT_CODE AS plant_code,
    pm.PLANT_NAME AS plant_name,
    
    -- Region 層級
    sm.REGION_CODE AS region_code,
    sm.REGION_NAME AS region_name,
    
    -- 資料品質標記
    CASE 
        WHEN ld.LINE_NAME IS NOT NULL 
         AND fa.FACTORY IS NOT NULL 
         AND pm.PLANT_CODE IS NOT NULL 
         AND sm.REGION_CODE IS NOT NULL 
        THEN 1 
        ELSE 0 
    END AS is_valid,
    
    now64(3) AS _mview_update_time

FROM bronze.common_mdm_line_desc_master ld
LEFT JOIN bronze.common_mdm_factory_area_master fa 
    ON ld.FACTORY = fa.FACTORY
LEFT JOIN bronze.common_mdm_mfg_plant_master pm 
    ON fa.PLANT_CODE = pm.PLANT_CODE  
LEFT JOIN bronze.common_mdm_mfg_site_master sm 
    ON pm.MFG_SITE = sm.MFG_SITE
WHERE ld.LINE_NAME IS NOT NULL 
  AND ld.LINE_NAME != '';

-- ========================================
-- 3. 核心事實表 - 實作 VARINST 優先，MDM 補齊
-- ========================================

DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution_mdm;

CREATE MATERIALIZED VIEW silver.mv_fact_task_vx_attribution_mdm
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (task_id)
SETTINGS allow_nullable_key = 1
POPULATE
AS
WITH 
-- 取得 VARINST 維度值
varinst_dimensions AS (
    SELECT 
        t.PROC_INST_ID_,
        v.varinst_region AS varinst_region,
        v.varinst_plant AS varinst_plant,
        v.varinst_factory AS varinst_factory,
        v.varinst_lineName AS varinst_line
    FROM bronze.bpm_act_hi_taskinst t
    LEFT JOIN silver.mv_varinst_pivoted v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
    WHERE t.ID_ IS NOT NULL AND t.ID_ != ''
),

-- 取得 MDM 維度值（透過 lineName 串接）
mdm_dimensions AS (
    SELECT 
        vd.PROC_INST_ID_,
        mdm.region_code AS mdm_region,
        mdm.region_name AS mdm_region_name,
        mdm.plant_code AS mdm_plant,
        mdm.plant_name AS mdm_plant_name,
        mdm.factory_code AS mdm_factory,
        mdm.factory_name AS mdm_factory_name,
        mdm.line_name AS mdm_line,
        mdm.line_desc AS mdm_line_desc,
        mdm.is_valid AS mdm_is_valid
    FROM varinst_dimensions vd
    LEFT JOIN silver.dim_mfg_five_level mdm ON vd.varinst_line = mdm.line_name
),

-- 實作維度補齊邏輯：VARINST 優先，MDM 補齊
dimension_backfill AS (
    SELECT 
        vd.PROC_INST_ID_,
        
        -- VARINST 原始值
        vd.varinst_region,
        vd.varinst_plant,
        vd.varinst_factory,
        vd.varinst_line,
        
        -- MDM 補齊值
        md.mdm_region,
        md.mdm_region_name,
        md.mdm_plant,
        md.mdm_plant_name,
        md.mdm_factory,
        md.mdm_factory_name,
        md.mdm_line,
        md.mdm_line_desc,
        md.mdm_is_valid,
        
        -- 最終值：VARINST 優先，缺失時用 MDM 補齊
        COALESCE(NULLIF(vd.varinst_region, ''), md.mdm_region) AS final_region,
        COALESCE(NULLIF(vd.varinst_plant, ''), md.mdm_plant) AS final_plant,
        COALESCE(NULLIF(vd.varinst_factory, ''), md.mdm_factory) AS final_factory,
        COALESCE(NULLIF(vd.varinst_line, ''), md.mdm_line) AS final_line,
        
        -- 資料來源標記
        CASE 
            WHEN vd.varinst_region IS NOT NULL AND vd.varinst_region != '' THEN 'VARINST'
            WHEN md.mdm_region IS NOT NULL AND md.mdm_region != '' THEN 'MDM'
            ELSE 'MISSING'
        END AS region_source,
        
        CASE 
            WHEN vd.varinst_plant IS NOT NULL AND vd.varinst_plant != '' THEN 'VARINST'
            WHEN md.mdm_plant IS NOT NULL AND md.mdm_plant != '' THEN 'MDM'
            ELSE 'MISSING'
        END AS plant_source,
        
        CASE 
            WHEN vd.varinst_factory IS NOT NULL AND vd.varinst_factory != '' THEN 'VARINST'
            WHEN md.mdm_factory IS NOT NULL AND md.mdm_factory != '' THEN 'MDM'
            ELSE 'MISSING'
        END AS factory_source,
        
        CASE 
            WHEN vd.varinst_line IS NOT NULL AND vd.varinst_line != '' THEN 'VARINST'
            WHEN md.mdm_line IS NOT NULL AND md.mdm_line != '' THEN 'MDM'
            ELSE 'MISSING'
        END AS line_source,
        
        -- 整體維度來源標記（向後相容）
        CASE 
            WHEN md.mdm_line IS NOT NULL THEN 'MDM_PRIMARY'
            WHEN vd.varinst_line IS NOT NULL THEN 'VARINST_FALLBACK'
            ELSE 'NO_DIMENSION'
        END AS dimension_source
        
    FROM varinst_dimensions vd
    LEFT JOIN mdm_dimensions md ON vd.PROC_INST_ID_ = md.PROC_INST_ID_
),

-- 建立日期展開邏輯（與 MSSQL 邏輯一致）
task_dates AS (
    SELECT 
        t.ID_ AS task_id,
        arrayDistinct(arrayFilter(x -> x IS NOT NULL, [
            toDate(t.START_TIME_),
            toDate(t.CLAIM_TIME_),
            toDate(t.END_TIME_)
        ])) AS task_dates_array
    FROM bronze.bpm_act_hi_taskinst t
    WHERE t.ID_ IS NOT NULL AND t.ID_ != ''
),

-- 展開每個任務到多個日期記錄
task_date_expanded AS (
    SELECT 
        task_id,
        arrayJoin(task_dates_array) AS task_create_date
    FROM task_dates
    WHERE length(task_dates_array) > 0
)

SELECT
    -- 主鍵（包含日期）
    concat(toString(t.ID_), '_', toString(tde.task_create_date)) AS task_id,
    t.ID_ AS original_task_id,
    
    -- 時間維度
    tde.task_create_date AS task_create_date,
    toDate(t.END_TIME_) AS task_end_date,
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
    
    -- Vx 歸屬邏輯
    CASE 
        WHEN COALESCE(v.varinst_moNumber, '') LIKE '196%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '315%'
        THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
        WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
        ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
    END AS vx_type,
    
    -- 五階維度（補齊後的最終值）
    COALESCE(db.final_plant, '') AS plant_code,
    COALESCE(db.mdm_plant_name, '') AS plant_name,
    COALESCE(db.final_factory, '') AS factory_code,
    COALESCE(db.mdm_factory_name, '') AS factory_name,
    COALESCE(db.final_line, '') AS line_code,
    COALESCE(db.final_line, '') AS line_name,
    COALESCE(db.final_region, '') AS region_code,
    COALESCE(db.mdm_region_name, '') AS region_name,
    
    -- 新增：個別維度的資料來源追蹤
    db.region_source,
    db.plant_source,
    db.factory_source,
    db.line_source,
    
    -- 整體維度來源標記（向後相容）
    db.dimension_source,
    
    -- 維度資料品質標記
    COALESCE(db.mdm_is_valid, 0) AS dimension_is_valid,
    
    -- 相容性欄位（語意修正：VARINST plant 對應 MDM factory）
    COALESCE(db.final_plant, '') AS plant,
    COALESCE(db.final_factory, '') AS factory,
    COALESCE(db.final_line, '') AS line,
    
    -- 新增：region 欄位（非 region_code）
    COALESCE(db.final_region, '') AS region,
    
    -- 排除標記
    CASE 
        WHEN COALESCE(CASE WHEN tb.LONG_ = 1 THEN 'Y' ELSE 'N' END, 'N') != 'N' THEN 1
        WHEN t.TASK_DEF_KEY_ LIKE 'E%' OR t.TASK_DEF_KEY_ LIKE 'C%' THEN 1
        WHEN COALESCE(v.varinst_moNumber, '') LIKE 'Q%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE 'R%' THEN 1
        ELSE 0
    END AS is_excluded,
    
    -- 排除原因
    CASE 
        WHEN COALESCE(CASE WHEN tb.LONG_ = 1 THEN 'Y' ELSE 'N' END, 'N') != 'N' THEN 'bypass'
        WHEN t.TASK_DEF_KEY_ LIKE 'E%' THEN 'E_prefix'
        WHEN t.TASK_DEF_KEY_ LIKE 'C%' THEN 'C_prefix'
        WHEN COALESCE(v.varinst_moNumber, '') LIKE 'Q%' THEN 'Q_order'
        WHEN COALESCE(v.varinst_moNumber, '') LIKE 'R%' THEN 'R_order'
        ELSE NULL
    END AS exclude_reason,
    
    -- 關聯欄位
    t.PROC_INST_ID_ AS proc_inst_id,
    p.BUSINESS_KEY_ AS business_key,
    COALESCE(v.varinst_moNumber, '') AS mo_number,
    p.NAME_ AS proc_name,
    
    -- Metadata
    now64(3) AS _mview_update_time

FROM bronze.bpm_act_hi_taskinst t
INNER JOIN task_date_expanded tde ON t.ID_ = tde.task_id
LEFT JOIN bronze.bpm_act_hi_procinst p ON t.PROC_INST_ID_ = p.PROC_INST_ID_
LEFT JOIN silver.mv_varinst_pivoted v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
LEFT JOIN bronze.common_hr_employee he ON t.ASSIGNEE_ = he.EmpCode
LEFT JOIN bronze.bpm_act_hi_varinst tb ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
LEFT JOIN dimension_backfill db ON t.PROC_INST_ID_ = db.PROC_INST_ID_
WHERE t.ID_ IS NOT NULL AND t.ID_ != '';

SELECT 'Silver layer views and mviews created successfully' AS status;