-- ========================================
-- ClickHouse 金銀銅資料層完整重建腳本
-- ========================================
-- 用途：重新建立所有 MVIEW，修正日期過濾邏輯問題
-- 執行時間：2026-01-23 16:00:00

-- ========================================
-- 清理現有 MVIEW（避免衝突）
-- ========================================

-- 清理 Gold 層
DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;
DROP VIEW IF EXISTS gold.vw_daily_l5_completion_summary;
DROP VIEW IF EXISTS gold.vw_vx_type_summary;
DROP VIEW IF EXISTS gold.vw_factory_summary;
DROP VIEW IF EXISTS gold.vw_v1_npe_mfg_comparison;

-- 清理 Silver 層
DROP TABLE IF EXISTS silver.mv_l5_metrics_realtime;
DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution;
DROP TABLE IF EXISTS silver.mv_dim_config_user;
DROP VIEW IF EXISTS silver.vw_fact_task_vx_attribution_realtime;
DROP VIEW IF EXISTS silver.vw_l5_metrics_mssql_compatible;

SELECT 'MVIEW 清理完成' AS status;

-- ========================================
-- 重建 Silver 層 MVIEW（修正版本）
-- ========================================

-- 1. 任務 Vx 歸屬事實表 MVIEW - 修正版本
CREATE MATERIALIZED VIEW silver.mv_fact_task_vx_attribution
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
    
    -- 預計算：V1 子類型
    CASE 
        -- 工單號規則的 V1 任務
        WHEN (COALESCE(v.varinst_moNumber, '') LIKE '196%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '315%')
             AND v.varinst_name LIKE '%NPE%'
        THEN 'V1_NPE'
        
        WHEN (COALESCE(v.varinst_moNumber, '') LIKE '196%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '315%')
        THEN 'V1_MFG'
        
        -- TaskDefinitionKey 的 V1 任務
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' AND v.varinst_name LIKE '%NPE%'
        THEN 'V1_NPE'
        
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%'
        THEN 'V1_MFG'
        
        ELSE NULL
    END AS vx_subtype,
    
    -- 是否套用特殊 V1 規則
    CASE 
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 1
        WHEN COALESCE(v.varinst_moNumber, '') LIKE '196%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '315%'
        THEN 1
        ELSE 0
    END AS is_special_v1_rule,
    
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
    
    -- 維度
    COALESCE(v.varinst_plant, '') AS plant,
    COALESCE(v.varinst_factory, '') AS factory,
    COALESCE(v.varinst_lineName, '') AS line,
    
    -- 關聯欄位
    t.PROC_INST_ID_ AS proc_inst_id,
    p.BUSINESS_KEY_ AS business_key,
    COALESCE(v.varinst_moNumber, '') AS mo_number,
    p.NAME_ AS proc_name,
    
    -- Metadata
    now64(3) AS _mview_update_time

FROM bronze.bpm_act_hi_taskinst t
LEFT JOIN bronze.bpm_act_hi_procinst p 
    ON t.PROC_INST_ID_ = p.PROC_INST_ID_
LEFT JOIN silver.mv_varinst_pivoted v
    ON t.PROC_INST_ID_ = v.PROC_INST_ID_
LEFT JOIN bronze.common_hr_employee he
    ON t.ASSIGNEE_ = he.EmpCode
LEFT JOIN bronze.bpm_act_hi_varinst tb
    ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
WHERE t.ID_ IS NOT NULL 
  AND t.ID_ != '';

SELECT 'Silver 事實表 MVIEW 建立完成' AS status;

-- 2. L5 指標聚合 MVIEW（修正版本）
CREATE MATERIALIZED VIEW silver.mv_l5_metrics_realtime
ENGINE = SummingMergeTree()
ORDER BY (task_create_date, task_claim_date, task_end_date, vx_type, vx_subtype, plant, factory, line)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT
    -- 修正：儲存所有三個日期，讓查詢時可以使用 MSSQL 的 OR 邏輯
    toDate(task_create_time) AS task_create_date,
    toDateOrNull(task_claim_time) AS task_claim_date,
    toDateOrNull(task_end_time) AS task_end_date,
    
    vx_type,
    vx_subtype,
    plant,
    factory,
    line,
    
    -- 基礎統計（只計算未排除的任務）
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
    
    -- V1 特殊規則統計
    countIf(is_special_v1_rule = 1) AS special_v1_rule_qty,
    
    now64(3) AS _mview_update_time
    
FROM silver.mv_fact_task_vx_attribution
GROUP BY 
    task_create_date,
    task_claim_date,
    task_end_date,
    vx_type,
    vx_subtype,
    plant,
    factory,
    line;

SELECT 'Silver 指標聚合 MVIEW 建立完成' AS status;

-- 3. 建立查詢視圖
CREATE VIEW silver.vw_fact_task_vx_attribution_realtime AS
SELECT 
    task_id,
    task_create_date,
    task_end_date,
    task_create_time,
    task_claim_time,
    task_end_time,
    task_status,
    task_bypass,
    task_definition_key,
    task_name,
    task_assignee_name,
    task_assignee_account,
    vx_type,
    vx_subtype,
    is_special_v1_rule,
    is_excluded,
    exclude_reason,
    plant,
    factory,
    line,
    proc_inst_id,
    business_key,
    mo_number,
    proc_name,
    _mview_update_time AS _transform_time
FROM silver.mv_fact_task_vx_attribution FINAL;

SELECT 'Silver 查詢視圖建立完成' AS status;

-- ========================================
-- 重建 Gold 層 MVIEW
-- ========================================

CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
ENGINE = ReplacingMergeTree()
ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT 
    -- 使用修正的日期邏輯：任何一個時間欄位的日期作為快照日期
    CASE 
        WHEN task_create_date IS NOT NULL THEN task_create_date
        WHEN task_claim_date IS NOT NULL THEN task_claim_date
        WHEN task_end_date IS NOT NULL THEN task_end_date
        ELSE toDate('1970-01-01')
    END AS snapshot_date,
    
    plant,
    factory,
    line,
    vx_type,
    vx_subtype,
    
    -- 任務數量統計
    SUM(total_task_qty) AS sum_total_task_qty,
    SUM(todo_qty) AS sum_todo_qty,
    SUM(doing_qty) AS sum_doing_qty,
    SUM(done_qty) AS sum_done_qty,
    
    -- 排除統計
    SUM(excluded_qty) AS sum_excluded_qty,
    SUM(bypass_qty) AS sum_bypass_qty,
    SUM(e_prefix_qty) AS sum_e_prefix_qty,
    SUM(c_prefix_qty) AS sum_c_prefix_qty,
    SUM(q_order_qty) AS sum_q_order_qty,
    SUM(r_order_qty) AS sum_r_order_qty,
    SUM(special_v1_rule_qty) AS sum_special_v1_rule_qty,
    
    -- 完成率計算
    CASE 
        WHEN SUM(total_task_qty) > 0 
        THEN ROUND(SUM(done_qty) * 100.0 / SUM(total_task_qty), 2)
        ELSE 0.0
    END AS completion_rate,
    
    -- 進行中率計算
    CASE 
        WHEN SUM(total_task_qty) > 0 
        THEN ROUND((SUM(doing_qty) + SUM(done_qty)) * 100.0 / SUM(total_task_qty), 2)
        ELSE 0.0
    END AS progress_rate,
    
    now64(3) AS _mview_update_time
    
FROM silver.mv_l5_metrics_realtime
GROUP BY 
    snapshot_date,
    plant,
    factory,
    line,
    vx_type,
    vx_subtype;

SELECT 'Gold 層 MVIEW 建立完成' AS status;

-- ========================================
-- 執行關鍵驗證查詢
-- ========================================

SELECT '=== Bronze 層驗證 ===' AS stage;
SELECT 'Bronze 層 BPM 任務表' AS check_name, COUNT(*) AS record_count
FROM bronze.bpm_act_hi_taskinst;

SELECT '=== Silver 層驗證 ===' AS stage;
SELECT 'Silver 層事實表' AS check_name, COUNT(*) AS record_count
FROM silver.mv_fact_task_vx_attribution FINAL;

SELECT '=== 關鍵測試案例 ===' AS stage;
-- WJ2/NBU/E5 2025-12-25 應為 5 筆（與 MSSQL 一致）
SELECT 'WJ2/NBU/E5 2025-12-25 測試' AS check_name, COUNT(*) AS record_count
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE (
    toDate(task_create_time) = '2025-12-25'
    OR toDate(task_claim_time) = '2025-12-25'
    OR toDate(task_end_time) = '2025-12-25'
)
AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5';

SELECT '=== Gold 層驗證 ===' AS stage;
SELECT 'Gold 層聚合表' AS check_name, COUNT(*) AS record_count
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL;

-- ========================================
-- 完成提示
-- ========================================
SELECT 
    '🎉 ClickHouse 金銀銅資料層重建完成' AS status,
    now() AS completion_time,
    'Bronze → Silver → Gold 資料流已修正' AS description;