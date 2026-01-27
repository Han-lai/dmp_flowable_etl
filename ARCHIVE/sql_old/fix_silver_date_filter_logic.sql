-- ============================================
-- 修正 Silver 層日期過濾邏輯
-- 問題：Silver MVIEW 只檢查 task_create_time，應該要像 MSSQL 一樣檢查 START_TIME_, CLAIM_TIME_, END_TIME_
-- 修正時間: 2026-01-23 14:45:00
-- ============================================

-- 1. 備份當前的 Silver MVIEW (如果需要回滾)
CREATE TABLE IF NOT EXISTS silver.mv_fact_task_vx_attribution_backup AS
SELECT * FROM silver.mv_fact_task_vx_attribution FINAL;

-- 2. 刪除有問題的 Silver MVIEW
DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution;

-- 3. 重建 Silver MVIEW，修正日期過濾邏輯
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
    
    -- 預計算：V1 子類型（修正後的邏輯：工單號規則優先，NPE 判別使用 varinst_name 欄位）
    CASE 
        -- 工單號規則的 V1 任務（無論原始 TaskDefinitionKey 是什麼）
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
        
        -- TaskDefinitionKey 的 V1 任務（工單號規則不符合時）
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' AND v.varinst_name LIKE '%NPE%'
        THEN 'V1_NPE'
        
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%'
        THEN 'V1_MFG'
        
        -- 其他情況（V2/V3 等）
        ELSE NULL
    END AS vx_subtype,
    
    -- 是否套用特殊 V1 規則（修正後的邏輯：工單號規則優先）
    CASE 
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 1
        -- 工單號規則（196/199/200/210/212/213/315 開頭）
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
-- TaskBypass 來自任務層級變數 autoComplete
LEFT JOIN bronze.bpm_act_hi_varinst tb
    ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
WHERE t.ID_ IS NOT NULL 
  AND t.ID_ != '';

-- 4. 重建 L5 指標聚合 MVIEW，修正日期過濾邏輯
DROP TABLE IF EXISTS silver.mv_l5_metrics_realtime;

CREATE MATERIALIZED VIEW silver.mv_l5_metrics_realtime
ENGINE = SummingMergeTree()
ORDER BY (snapshot_date, vx_type, vx_subtype, plant, factory, line)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT
    toDateOrNull(task_create_time) AS snapshot_date,
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
    snapshot_date,
    vx_type,
    vx_subtype,
    plant,
    factory,
    line;

-- 5. 更新查詢視圖
DROP VIEW IF EXISTS silver.vw_fact_task_vx_attribution_realtime;

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

-- 6. 驗證修正結果
SELECT 
    'Silver MVIEW 修正驗證' as check_type,
    COUNT(*) as total_records,
    COUNT(DISTINCT task_id) as unique_tasks
FROM silver.mv_fact_task_vx_attribution FINAL;

-- 7. 驗證 2025-12-25 WJ2/NBU/E5 的記錄數
SELECT 
    'WJ2/NBU/E5 2025-12-25 驗證' as check_type,
    COUNT(*) as record_count,
    COUNT(DISTINCT task_id) as unique_tasks
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE toDate(task_create_time) = '2025-12-25'
AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5';

SELECT 'Silver 層修正完成' AS status;