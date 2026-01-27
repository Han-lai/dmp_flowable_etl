-- ========================================
-- L5 指標 MDM 五階維度更新
-- 將 L5 指標從三維度升級為五維度
-- 日期：2026-01-21
-- ========================================

-- ========================================
-- 步驟 1：驗證 Silver 層事實表
-- ========================================

-- 檢查現有的任務事實表
SELECT 
    'Silver 層任務事實表驗證' as status,
    count() as total_tasks,
    count(DISTINCT line) as unique_lines,
    count(DISTINCT plant) as unique_plants,
    count(DISTINCT factory) as unique_factories
FROM silver.mv_fact_task_vx_attribution;

-- ========================================
-- 步驟 2：建立五階維度增強的任務視圖
-- ========================================

DROP VIEW IF EXISTS silver.vw_fact_task_with_five_level;

CREATE VIEW silver.vw_fact_task_with_five_level AS
SELECT
    -- 原有欄位
    t.task_id,
    t.task_create_date,
    t.task_end_date,
    t.task_create_time,
    t.task_status,
    t.vx_type,
    t.vx_subtype,
    t.is_excluded,
    t.exclude_reason,
    t.plant,
    t.factory,
    t.line,
    
    -- 新增：五階維度欄位
    d.region_code,
    d.region_name,
    t.vx_type as vx_code,
    CASE t.vx_type 
        WHEN 'V1' THEN 'Version 1'
        WHEN 'V2' THEN 'Version 2'
        WHEN 'V3' THEN 'Version 3'
        ELSE 'Unknown'
    END as vx_name,
    d.plant_code,
    d.plant_name,
    d.factory_code,
    d.factory_name,
    d.line_code,
    d.line_desc as line_name,
    
    -- 新增：五階維度完整性標記
    CASE 
        WHEN d.region_code IS NOT NULL 
         AND d.plant_code IS NOT NULL 
         AND d.factory_code IS NOT NULL 
         AND d.line_code IS NOT NULL 
        THEN 1 
        ELSE 0 
    END as five_level_complete
    
FROM silver.mv_fact_task_vx_attribution t
LEFT JOIN silver.dim_mfg_five_level d
    ON t.line = d.line_code;

-- ========================================
-- 步驟 3：驗證五階維度增強視圖
-- ========================================

SELECT 
    '五階維度增強視圖驗證' as status,
    count() as total_tasks,
    sum(five_level_complete) as five_level_complete_tasks,
    round(sum(five_level_complete) * 100.0 / count(), 2) as five_level_complete_rate
FROM silver.vw_fact_task_with_five_level;

-- ========================================
-- 步驟 4：建立五階維度 L5 指標聚合視圖
-- ========================================

DROP VIEW IF EXISTS silver.vw_l5_metrics_five_level;

CREATE VIEW silver.vw_l5_metrics_five_level AS
SELECT
    toDate(task_create_time) AS snapshot_date,
    vx_type,
    vx_subtype,
    
    -- 五階維度
    region_code,
    region_name,
    plant_code,
    plant_name,
    factory_code,
    factory_name,
    line_code,
    line_name,
    
    -- 基礎統計（只計算五階維度完整且未排除的任務）
    countIf(is_excluded = 0 AND five_level_complete = 1) AS total_task_qty,
    countIf(is_excluded = 0 AND five_level_complete = 1 AND task_status = 'TODO') AS todo_qty,
    countIf(is_excluded = 0 AND five_level_complete = 1 AND task_status = 'DOING') AS doing_qty,
    countIf(is_excluded = 0 AND five_level_complete = 1 AND task_status = 'DONE') AS done_qty,
    countIf(is_excluded = 0 AND five_level_complete = 1 AND task_status IN ('DOING', 'DONE')) AS doing_done_qty,
    countIf(is_excluded = 0 AND five_level_complete = 1 AND task_status IN ('TODO', 'DOING')) AS todo_doing_acc_qty,
    
    -- 排除統計
    countIf(is_excluded = 1) AS excluded_qty,
    
    -- 五階維度完整性統計
    countIf(five_level_complete = 1) AS five_level_complete_qty,
    countIf(five_level_complete = 0) AS five_level_incomplete_qty
    
FROM silver.vw_fact_task_with_five_level
WHERE region_code IS NOT NULL
  AND plant_code IS NOT NULL
  AND factory_code IS NOT NULL
  AND line_code IS NOT NULL
GROUP BY 
    snapshot_date,
    vx_type,
    vx_subtype,
    region_code,
    region_name,
    plant_code,
    plant_name,
    factory_code,
    factory_name,
    line_code,
    line_name;

-- ========================================
-- 步驟 5：驗證 L5 指標聚合
-- ========================================

SELECT 
    '五階維度 L5 指標聚合驗證' as status,
    count() as metric_rows,
    count(DISTINCT snapshot_date) as unique_dates,
    count(DISTINCT region_code) as unique_regions,
    count(DISTINCT plant_code) as unique_plants,
    count(DISTINCT factory_code) as unique_factories,
    count(DISTINCT line_code) as unique_lines
FROM silver.vw_l5_metrics_five_level;

-- ========================================
-- 步驟 6：驗證具體範例
-- ========================================

SELECT 
    snapshot_date,
    vx_type,
    region_code,
    plant_code,
    factory_code,
    line_code,
    total_task_qty,
    done_qty,
    CASE WHEN total_task_qty > 0 THEN round(done_qty * 100.0 / total_task_qty, 2) ELSE 0 END as completion_rate
FROM silver.vw_l5_metrics_five_level
WHERE region_code = 'WJ'
  AND plant_code = 'WJ2'
  AND factory_code = 'PF'
  AND line_code = 'E5'
ORDER BY snapshot_date DESC
LIMIT 10;
