-- ========================================
-- 測試 MSSQL 日期過濾邏輯一致性
-- ========================================
-- 目的：驗證修正後的 ClickHouse 查詢是否與 MSSQL 參考查詢結果一致
-- 測試條件：2025-12-25, WJ2/NBU/E5
-- 預期結果：5 筆記錄

-- ========================================
-- 1. 使用與 MSSQL 一致的日期過濾邏輯查詢
-- ========================================

SELECT 
    'MSSQL 相容查詢 - WJ2/NBU/E5 2025-12-25' AS test_name,
    COUNT(*) AS record_count,
    COUNT(DISTINCT task_id) AS unique_tasks
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE (
    -- 與 MSSQL 一致的 OR 邏輯：任何一個時間欄位在指定日期即包含
    toDate(task_create_time) = '2025-12-25'
    OR toDate(task_claim_time) = '2025-12-25'
    OR toDate(task_end_time) = '2025-12-25'
)
AND plant = 'WJ2' 
AND factory = 'NBU' 
AND line = 'E5';

-- ========================================
-- 2. 詳細記錄比對
-- ========================================

SELECT 
    task_id,
    task_definition_key,
    task_name,
    task_status,
    task_bypass,
    task_assignee_account,
    task_assignee_name,
    formatDateTime(task_create_time, '%Y-%m-%d %H:%i:%s') AS task_create_time,
    formatDateTime(task_claim_time, '%Y-%m-%d %H:%i:%s') AS task_claim_time,
    formatDateTime(task_end_time, '%Y-%m-%d %H:%i:%s') AS task_end_time,
    plant,
    factory,
    line,
    mo_number,
    vx_type,
    vx_subtype
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE (
    toDate(task_create_time) = '2025-12-25'
    OR toDate(task_claim_time) = '2025-12-25'
    OR toDate(task_end_time) = '2025-12-25'
)
AND plant = 'WJ2' 
AND factory = 'NBU' 
AND line = 'E5'
ORDER BY task_create_time;

-- ========================================
-- 3. 與原始查詢方式比較
-- ========================================

SELECT 
    'Original 查詢方式 - 只檢查 task_create_time' AS test_name,
    COUNT(*) AS record_count,
    COUNT(DISTINCT task_id) AS unique_tasks
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE toDate(task_create_time) = '2025-12-25'
AND plant = 'WJ2' 
AND factory = 'NBU' 
AND line = 'E5';

-- ========================================
-- 4. 檢查各時間欄位的分布
-- ========================================

SELECT 
    'Time Field Distribution' AS analysis_type,
    COUNT(*) AS total_records,
    countIf(toDate(task_create_time) = '2025-12-25') AS create_time_matches,
    countIf(toDate(task_claim_time) = '2025-12-25') AS claim_time_matches,
    countIf(toDate(task_end_time) = '2025-12-25') AS end_time_matches,
    countIf(
        toDate(task_create_time) = '2025-12-25'
        OR toDate(task_claim_time) = '2025-12-25'
        OR toDate(task_end_time) = '2025-12-25'
    ) AS or_logic_matches
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE plant = 'WJ2' 
AND factory = 'NBU' 
AND line = 'E5';

-- ========================================
-- 5. Bronze 層驗證
-- ========================================

SELECT 
    'Bronze 層驗證 - WJ2/NBU/E5 2025-12-25' AS test_name,
    COUNT(*) AS record_count
FROM bronze.bpm_act_hi_taskinst t
LEFT JOIN silver.mv_varinst_pivoted v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
WHERE (
    toDate(t.START_TIME_) = '2025-12-25'
    OR toDate(t.CLAIM_TIME_) = '2025-12-25'
    OR toDate(t.END_TIME_) = '2025-12-25'
)
AND v.varinst_plant = 'WJ2'
AND v.varinst_factory = 'NBU'
AND v.varinst_lineName = 'E5';

SELECT 'Date Filter Logic Test Completed' AS status;