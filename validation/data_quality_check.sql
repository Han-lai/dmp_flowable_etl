-- ============================================
-- 資料品質檢查查詢
-- 檢查 Primary Key 唯一性、非空欄位、時間欄位範圍
-- ============================================

-- ============================================
-- 1. Primary Key 唯一性檢查
-- ============================================
SELECT 
    'bpm_act_hi_procinst' as table_name,
    count(*) as total_rows,
    count(distinct ID_) as unique_ids,
    count(*) - count(distinct ID_) as duplicates
FROM bronze.bpm_act_hi_procinst

UNION ALL

SELECT 
    'bpm_act_hi_taskinst',
    count(*),
    count(distinct ID_),
    count(*) - count(distinct ID_)
FROM bronze.bpm_act_hi_taskinst

UNION ALL

SELECT 
    'common_flowable_task_stats',
    count(*),
    count(distinct TaskId),
    count(*) - count(distinct TaskId)
FROM bronze.common_flowable_task_stats

UNION ALL

SELECT 
    'common_hr_employee',
    count(*),
    count(distinct EmpCode),
    count(*) - count(distinct EmpCode)
FROM bronze.common_hr_employee;

-- ============================================
-- 2. 非空欄位檢查（關鍵欄位）
-- ============================================
SELECT 
    'bpm_act_hi_procinst' as table_name,
    'ID_' as column_name,
    countIf(ID_ = '' OR ID_ IS NULL) as null_count,
    count(*) as total_count
FROM bronze.bpm_act_hi_procinst

UNION ALL

SELECT 
    'bpm_act_hi_procinst',
    'PROC_INST_ID_',
    countIf(PROC_INST_ID_ = '' OR PROC_INST_ID_ IS NULL),
    count(*)
FROM bronze.bpm_act_hi_procinst;


-- ============================================
-- 3. 時間欄位範圍檢查
-- ============================================
SELECT 
    'bpm_act_hi_procinst' as table_name,
    min(START_TIME_) as min_time,
    max(START_TIME_) as max_time,
    count(*) as total_rows
FROM bronze.bpm_act_hi_procinst

UNION ALL

SELECT 
    'bpm_act_hi_taskinst',
    min(START_TIME_),
    max(START_TIME_),
    count(*)
FROM bronze.bpm_act_hi_taskinst

UNION ALL

SELECT 
    'common_flowable_task_stats',
    min(TaskCreateTime),
    max(TaskCreateTime),
    count(*)
FROM bronze.common_flowable_task_stats;

-- ============================================
-- 4. 資料分佈檢查（按月份）
-- ============================================
SELECT 
    toYYYYMM(START_TIME_) as month,
    count(*) as row_count
FROM bronze.bpm_act_hi_procinst
GROUP BY month
ORDER BY month DESC
LIMIT 12;

-- ============================================
-- 5. 同步狀態檢查
-- ============================================
SELECT 
    source_db,
    table_name,
    sync_type,
    status,
    start_time,
    end_time,
    rows_written,
    error_message
FROM bronze._sync_log
ORDER BY start_time DESC
LIMIT 20;
