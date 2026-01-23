-- ========================================
-- 修正 Silver 層時間邏輯，與 MSSQL 查詢邏輯統一
-- ========================================
-- 目的：讓 ClickHouse MVIEW 的時間邏輯與 MSSQL 查詢一致
-- 邏輯：任務在某日期出現，當且僅當 START_TIME_, CLAIM_TIME_, END_TIME_ 任一在該日期範圍內

-- 重建 Silver 層 MVIEW，使用統一的時間邏輯
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
),

-- 建立日期展開邏輯（與 MSSQL 邏輯一致）
task_dates AS (
    SELECT 
        t.ID_ AS task_id,
        
        -- 收集所有可能的日期（與 MSSQL BETWEEN 邏輯一致）
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
    -- 主鍵（包含日期，因為一個任務可能對應多個日期）
    concat(toString(t.ID_), '_', toString(tde.task_create_date)) AS task_id,
    t.ID_ AS original_task_id,
    
    -- 時間維度（修正後的邏輯）
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
    
    -- Plant 層級（修正：Flowable factory 對應 Plant）
    COALESCE(
        dm.mdm_plant,
        dm.flowable_factory,
        dm.business_key_plant,
        ''
    ) AS plant_code,
    COALESCE(dm.mdm_plant_name, '') AS plant_name,
    
    -- Factory 層級（修正：Flowable plant 對應 Factory）
    COALESCE(
        dm.mdm_factory,
        dm.flowable_plant,
        ''
    ) AS factory_code,
    COALESCE(dm.mdm_factory_name, '') AS factory_name,
    
    -- Line 層級
    COALESCE(
        dm.mdm_line,
        dm.flowable_line,
        ''
    ) AS line_code,
    COALESCE(dm.mdm_line_desc, '') AS line_name,
    
    -- Region 層級
    COALESCE(dm.mdm_region, '') AS region_code,
    COALESCE(dm.mdm_region_name, '') AS region_name,
    
    -- 維度資料來源標記
    CASE 
        WHEN dm.mdm_line IS NOT NULL THEN 'MDM_PRIMARY'
        WHEN dm.flowable_line IS NOT NULL THEN 'FLOWABLE_FALLBACK'
        WHEN dm.business_key_plant IS NOT NULL THEN 'BUSINESS_KEY_FALLBACK'
        ELSE 'NO_DIMENSION'
    END AS dimension_source,
    
    -- 維度資料品質標記
    COALESCE(dm.mdm_is_valid, 0) AS dimension_is_valid,
    
    -- 相容性欄位
    COALESCE(
        dm.mdm_plant,
        dm.flowable_factory,
        dm.business_key_plant,
        ''
    ) AS plant,
    
    COALESCE(
        dm.mdm_factory,
        dm.flowable_plant,
        ''
    ) AS factory,
    
    COALESCE(
        dm.mdm_line,
        dm.flowable_line,
        ''
    ) AS line,
    
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

-- 重建 L5 指標聚合 MVIEW
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
    
    -- 完整五階維度
    region_code,
    plant_code,
    factory_code,
    line_code,
    
    -- 維度名稱
    region_name,
    plant_name,
    factory_name,
    line_name,
    
    -- 維度資料來源
    dimension_source,
    
    -- 基礎統計（只計算未排除的任務，避免重複計算）
    countIf(is_excluded = 0) AS total_task_qty,
    countIf(is_excluded = 0 AND task_status = 'TODO') AS todo_qty,
    countIf(is_excluded = 0 AND task_status = 'DOING') AS doing_qty,
    countIf(is_excluded = 0 AND task_status = 'DONE') AS done_qty,
    
    -- 排除統計
    countIf(is_excluded = 1) AS excluded_qty,
    countIf(exclude_reason = 'bypass') AS bypass_qty,
    countIf(exclude_reason = 'E_prefix') AS e_prefix_qty,
    countIf(exclude_reason = 'C_prefix') AS c_prefix_qty,
    countIf(exclude_reason = 'Q_order') AS q_order_qty,
    countIf(exclude_reason = 'R_order') AS r_order_qty,
    
    -- 維度品質統計
    countIf(dimension_source = 'MDM_PRIMARY') AS mdm_primary_qty,
    countIf(dimension_source = 'FLOWABLE_FALLBACK') AS flowable_fallback_qty,
    countIf(dimension_source = 'BUSINESS_KEY_FALLBACK') AS business_key_fallback_qty,
    countIf(dimension_source = 'NO_DIMENSION') AS no_dimension_qty,
    
    now64(3) AS _mview_update_time
    
FROM silver.mv_fact_task_vx_attribution_mdm
GROUP BY 
    snapshot_date,
    vx_type,
    region_code,
    plant_code,
    factory_code,
    line_code,
    region_name,
    plant_name,
    factory_name,
    line_name,
    dimension_source;

-- 建立完成提示
SELECT 'Silver Layer Time Logic Updated Successfully' AS status,
       'Time logic now matches MSSQL BETWEEN conditions' AS description,
       'Tasks appear on dates when START_TIME, CLAIM_TIME, or END_TIME falls within that date' AS logic;