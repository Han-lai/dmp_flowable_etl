-- ========================================
-- 步驟 4: Silver Layer - Fact Tasks (Vx)
-- 內容: mv_fact_task_vx (Core Fact Table)
-- 前置: 03_silver_pivot_and_hierarchy
-- ========================================

-- 啟用 REFRESHABLE MView 實驗功能
SET allow_experimental_refreshable_materialized_view = 1;

-- DROP TABLE IF EXISTS silver.mv_fact_task_vx;

CREATE MATERIALIZED VIEW silver.mv_fact_task_vx
REFRESH EVERY 1 DAY OFFSET 3 HOUR
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (task_id)
TTL task_primary_date + INTERVAL 1 YEAR
SETTINGS allow_nullable_key = 1
AS
SELECT
    t.ID_ AS task_id,
    
    -- ========================================
    -- 多時間維度 (匹配原始 L5 SQL 邏輯)
    -- 原始 SQL: START_TIME OR CLAIM_TIME OR END_TIME BETWEEN ...
    -- ========================================
    toDate(t.START_TIME_) AS task_start_date,        -- 任務建立日期
    toDate(t.CLAIM_TIME_) AS task_claim_date,        -- 任務認領日期
    toDate(t.END_TIME_) AS task_end_date,            -- 任務完成日期
    toDate(COALESCE(t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_)) AS task_primary_date,  -- 主要日期 (用於 TTL)
    
    -- 保留原欄位名稱以相容舊查詢
    toDate(COALESCE(t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_)) AS task_create_date,
    
    -- 任務狀態
    CASE 
        WHEN t.END_TIME_ IS NOT NULL THEN 'DONE'
        WHEN t.ASSIGNEE_ IS NOT NULL AND t.ASSIGNEE_ != '' THEN 'DOING'
        ELSE 'TODO'
    END AS task_status,
    
    -- Vx 歸屬（廠區特權 > 工單號 > 任務定義鍵）
    CASE 
        -- 規則 1：DG3 廠區特權工單 -> 強制轉 V1
        WHEN COALESCE(NULLIF(mv_varinst_pivoted.varinst_plant, ''), mdm.plant_code, '') = 'DG3' 
             AND substring(COALESCE(mv_varinst_pivoted.varinst_moNumber, ''), 1, 3) IN ('196','199','200','210','212','213','315') 
        THEN 'V1'
        
        -- 規則 2：NPE 廠區特權工單 -> 強制轉 V1
        WHEN (
               COALESCE(NULLIF(mv_varinst_pivoted.varinst_factory, ''), mdm.factory_code, '') LIKE '%NPE%' 
               OR COALESCE(NULLIF(mv_varinst_pivoted.varinst_plant, ''), mdm.plant_code, '') LIKE '%NPE%'
             )
             AND substring(COALESCE(mv_varinst_pivoted.varinst_moNumber, ''), 1, 3) IN ('196','199','200','210','212','213','315') 
        THEN 'V1'
        
        -- 規則 3：回歸 TASK_DEF_KEY_
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
        WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
        
        ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
    END AS vx_type,
    
    -- 維度（VARINST 優先，MDM 補齊）
    COALESCE(NULLIF(mv_varinst_pivoted.varinst_region, ''), mdm.region_code, 'UNKNOWN') AS region,
    COALESCE(NULLIF(mv_varinst_pivoted.varinst_plant, ''), mdm.plant_code, 'UNKNOWN') AS plant,
    COALESCE(NULLIF(mv_varinst_pivoted.varinst_factory, ''), mdm.factory_code, 'UNKNOWN') AS factory,
    COALESCE(NULLIF(mv_varinst_pivoted.varinst_lineName, ''), mdm.line_name, 'UNKNOWN') AS line,
    
    -- 維度來源追蹤
    CASE WHEN mv_varinst_pivoted.varinst_region != '' THEN 'VARINST' 
         WHEN mdm.region_code IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS region_source,
    CASE WHEN mv_varinst_pivoted.varinst_plant != '' THEN 'VARINST'
         WHEN mdm.plant_code IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS plant_source,
    CASE WHEN mv_varinst_pivoted.varinst_factory != '' THEN 'VARINST'
         WHEN mdm.factory_code IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS factory_source,
    CASE WHEN mv_varinst_pivoted.varinst_lineName != '' THEN 'VARINST'
         WHEN mdm.line_name IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS line_source,
    
    -- 排除標記
    CASE 
        WHEN tb.LONG_ = 1 THEN 1  -- bypass
        WHEN t.TASK_DEF_KEY_ LIKE 'E%' OR t.TASK_DEF_KEY_ LIKE 'C%' THEN 1
        WHEN COALESCE(mv_varinst_pivoted.varinst_moNumber, '') LIKE 'Q%' 
             OR COALESCE(mv_varinst_pivoted.varinst_moNumber, '') LIKE 'R%' THEN 1
        WHEN t.NAME_ LIKE '%Notify%' OR t.NAME_ LIKE '%Dummy%' THEN 1
        ELSE 0
    END AS is_excluded,
    
    CASE 
        WHEN tb.LONG_ = 1 THEN 'bypass'
        WHEN t.TASK_DEF_KEY_ LIKE 'E%' THEN 'system_node'
        WHEN t.TASK_DEF_KEY_ LIKE 'C%' THEN 'system_node'
        WHEN COALESCE(mv_varinst_pivoted.varinst_moNumber, '') LIKE 'Q%' THEN 'Q_order'
        WHEN COALESCE(mv_varinst_pivoted.varinst_moNumber, '') LIKE 'R%' THEN 'R_order'
        WHEN t.NAME_ LIKE '%Notify%' THEN 'notify_task'
        WHEN t.NAME_ LIKE '%Dummy%' THEN 'dummy_task'
        ELSE ''
    END AS exclude_reason,
    
    -- 人員資訊
    t.ASSIGNEE_ AS assignee_code,
    he.EmpName AS assignee_name,
    
    -- 任務屬性
    t.TASK_DEF_KEY_ AS task_definition_key,
    t.NAME_ AS task_name,
    mv_varinst_pivoted.varinst_moNumber AS mo_number,
    t.PROC_INST_ID_ AS proc_inst_id,
    
    now64(3) AS _mview_update_time

FROM bronze.bpm_act_hi_taskinst t
LEFT JOIN silver.mv_varinst_pivoted ON t.PROC_INST_ID_ = mv_varinst_pivoted.PROC_INST_ID_
LEFT JOIN silver.mv_dim_mfg_five_level mdm ON mv_varinst_pivoted.varinst_lineName = mdm.line_name AND mv_varinst_pivoted.varinst_plant = mdm.plant_code
LEFT JOIN bronze.common_hr_employee he ON t.ASSIGNEE_ = he.EmpCode
LEFT JOIN bronze.bpm_act_hi_varinst tb ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
WHERE t.ID_ IS NOT NULL AND t.ID_ != '';

-- 驗證資料量
SELECT 'mv_fact_task_vx' AS table_name, count() AS row_count 
FROM silver.mv_fact_task_vx;

-- 驗證新增的時間維度欄位
SELECT 
    'time_dimensions' AS check_name,
    count() AS total,
    countIf(task_start_date IS NOT NULL) AS with_start_date,
    countIf(task_claim_date IS NOT NULL) AS with_claim_date,
    countIf(task_end_date IS NOT NULL) AS with_end_date
FROM silver.mv_fact_task_vx FINAL;

-- 驗證 Vx 分布
SELECT vx_type, count() AS cnt 
FROM silver.mv_fact_task_vx FINAL
GROUP BY vx_type 
ORDER BY cnt DESC;

SELECT 'Silver Layer 2 (v2 多時間維度) 完成' AS status;
