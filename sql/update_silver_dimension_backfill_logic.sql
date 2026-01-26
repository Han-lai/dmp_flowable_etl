-- ========================================
-- 更新 Silver 層維度補齊邏輯
-- 規則：VARINST 優先，MDM 補齊，並標記資料來源
-- ========================================

-- ========================================
-- 1. 更新核心事實表 MVIEW - 實作 VARINST 優先，MDM 補齊
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
        COALESCE(vd.varinst_region, md.mdm_region) AS final_region,
        COALESCE(vd.varinst_plant, md.mdm_plant) AS final_plant,
        COALESCE(vd.varinst_factory, md.mdm_factory) AS final_factory,
        COALESCE(vd.varinst_line, md.mdm_line) AS final_line,
        
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

-- ========================================
-- 2. 更新 L5 指標聚合 MVIEW
-- ========================================

DROP TABLE IF EXISTS silver.mv_l5_metrics_realtime_mdm;

CREATE MATERIALIZED VIEW silver.mv_l5_metrics_realtime_mdm
ENGINE = SummingMergeTree()
ORDER BY (snapshot_date, vx_type, region_code, plant_code, factory_code, line_code)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT
    task_create_date AS snapshot_date,
    vx_type,
    
    -- 完整五階維度（使用補齊後的值）
    region_code,
    plant_code,
    factory_code,
    line_code,
    
    -- 維度名稱
    region_name,
    plant_name,
    factory_name,
    line_name,
    
    -- 新增：維度資料來源統計
    region_source,
    plant_source,
    factory_source,
    line_source,
    dimension_source,
    
    -- 基礎統計
    countIf(is_excluded = 0) AS total_task_qty,
    countIf(is_excluded = 0 AND task_status = 'TODO') AS todo_qty,
    countIf(is_excluded = 0 AND task_status = 'DOING') AS doing_qty,
    countIf(is_excluded = 0 AND task_status = 'DONE') AS done_qty,
    
    -- 排除統計
    countIf(is_excluded = 1) AS excluded_qty,
    countIf(exclude_reason = 'bypass') AS bypass_qty,
    
    -- 維度來源統計
    countIf(region_source = 'VARINST') AS region_varinst_qty,
    countIf(region_source = 'MDM') AS region_mdm_qty,
    countIf(plant_source = 'VARINST') AS plant_varinst_qty,
    countIf(plant_source = 'MDM') AS plant_mdm_qty,
    countIf(factory_source = 'VARINST') AS factory_varinst_qty,
    countIf(factory_source = 'MDM') AS factory_mdm_qty,
    countIf(line_source = 'VARINST') AS line_varinst_qty,
    countIf(line_source = 'MDM') AS line_mdm_qty,
    
    now64(3) AS _mview_update_time
    
FROM silver.mv_fact_task_vx_attribution_mdm
GROUP BY 
    snapshot_date, vx_type,
    region_code, plant_code, factory_code, line_code,
    region_name, plant_name, factory_name, line_name,
    region_source, plant_source, factory_source, line_source, dimension_source;

-- ========================================
-- 3. 更新其他相關 Silver 層 mview
-- ========================================

-- 更新任務狀態摘要 mview（使用補齊後的維度）
DROP TABLE IF EXISTS silver.mv_task_status_summary;

CREATE MATERIALIZED VIEW silver.mv_task_status_summary
ENGINE = SummingMergeTree()
ORDER BY (snapshot_date, vx_type, plant, factory)
POPULATE
AS
SELECT
    task_create_date AS snapshot_date,
    vx_type,
    
    -- 使用補齊後的維度
    plant,
    factory,
    region,  -- 新增 region 維度
    
    -- 維度來源資訊
    plant_source,
    factory_source,
    region_source,
    
    -- 統計指標
    countIf(is_excluded = 0) AS total_tasks,
    countIf(is_excluded = 0 AND task_status = 'TODO') AS todo_tasks,
    countIf(is_excluded = 0 AND task_status = 'DOING') AS doing_tasks,
    countIf(is_excluded = 0 AND task_status = 'DONE') AS done_tasks,
    
    -- 完成率
    CASE 
        WHEN countIf(is_excluded = 0) > 0 
        THEN countIf(is_excluded = 0 AND task_status = 'DONE') * 100.0 / countIf(is_excluded = 0)
        ELSE 0
    END AS completion_rate,
    
    now64(3) AS _mview_update_time
    
FROM silver.mv_fact_task_vx_attribution_mdm
WHERE is_excluded = 0
GROUP BY 
    snapshot_date, vx_type, plant, factory, region,
    plant_source, factory_source, region_source;

-- ========================================
-- 建立完成提示
-- ========================================
SELECT 'Silver Layer Dimension Backfill Logic Updated Successfully' AS status,
       'Rule: VARINST Priority, MDM Backfill' AS rule,
       'Updated tables: mv_fact_task_vx_attribution_mdm, mv_l5_metrics_realtime_mdm, mv_task_status_summary' AS updated_tables,
       'New fields: region_source, plant_source, factory_source, line_source, region' AS new_fields;