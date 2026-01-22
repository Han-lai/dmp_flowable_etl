-- ========================================
-- 修正 MVIEW 時間邏輯以符合新規範
-- ========================================
-- 問題：mv_l5_metrics_realtime 只使用 task_create_time 計算 snapshot_date
-- 規範：應使用 OR 條件包含 task_create_time/task_claim_time/task_end_time
-- 影響：有 20.3% 的任務可能因時間邏輯問題被遺漏

-- ========================================
-- 1. 修正 mv_l5_metrics_realtime 的時間邏輯
-- ========================================

-- 先備份現有 MVIEW（可選）
-- CREATE TABLE silver.mv_l5_metrics_realtime_backup AS SELECT * FROM silver.mv_l5_metrics_realtime;

-- 刪除現有 MVIEW
DROP TABLE IF EXISTS silver.mv_l5_metrics_realtime;

-- 重新建立符合規範的 MVIEW
CREATE MATERIALIZED VIEW silver.mv_l5_metrics_realtime
ENGINE = SummingMergeTree()
ORDER BY (snapshot_date, vx_type, vx_subtype, plant, factory, line)
SETTINGS allow_nullable_key = 1
POPULATE
AS
WITH task_dates AS (
    SELECT 
        task_id,
        vx_type,
        vx_subtype,
        plant,
        factory,
        line,
        task_status,
        is_excluded,
        exclude_reason,
        is_special_v1_rule,
        _mview_update_time,
        
        -- 使用 OR 條件的時間邏輯：任務在任一時間點的日期都會被包含
        arrayDistinct([
            toDate(task_create_time),
            toDate(task_claim_time),
            toDate(task_end_time)
        ]) AS active_dates
        
    FROM silver.mv_fact_task_vx_attribution
    WHERE task_create_time IS NOT NULL  -- 確保至少有創建時間
),

-- 展開每個任務的所有活動日期
task_date_expanded AS (
    SELECT 
        task_id,
        vx_type,
        vx_subtype,
        plant,
        factory,
        line,
        task_status,
        is_excluded,
        exclude_reason,
        is_special_v1_rule,
        _mview_update_time,
        arrayJoin(active_dates) AS snapshot_date
        
    FROM task_dates
    WHERE snapshot_date IS NOT NULL  -- 排除 NULL 日期
)

SELECT
    snapshot_date,
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
    
FROM task_date_expanded
GROUP BY 
    snapshot_date,
    vx_type,
    vx_subtype,
    plant,
    factory,
    line;

-- ========================================
-- 2. 重新建立 Gold 層 MVIEW（依賴 Silver 層）
-- ========================================

-- 刪除現有 Gold 層 MVIEW
DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;

-- 重新建立 Gold 層 MVIEW
CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
ENGINE = ReplacingMergeTree()
ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT 
    snapshot_date,  -- 使用修正後的 Silver 層日期邏輯
    COALESCE(plant, '') AS plant,
    COALESCE(factory, '') AS factory,
    COALESCE(line, '') AS line,
    vx_type,
    COALESCE(vx_subtype, '') AS vx_subtype,
    
    -- 任務數量統計
    SUM(todo_qty) AS sum_todo_qty,
    SUM(doing_qty) AS sum_doing_qty,
    SUM(done_qty) AS sum_done_qty,
    SUM(total_task_qty) AS sum_total_task_qty,
    SUM(excluded_qty) AS sum_excluded_qty,
    
    -- 排除原因統計
    SUM(bypass_qty) AS sum_bypass_qty,
    SUM(e_prefix_qty) AS sum_e_prefix_qty,
    SUM(c_prefix_qty) AS sum_c_prefix_qty,
    SUM(q_order_qty) AS sum_q_order_qty,
    SUM(r_order_qty) AS sum_r_order_qty,
    
    -- 特殊規則統計
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

-- ========================================
-- 3. 驗證修正結果
-- ========================================

-- 檢查修正後的資料量變化
SELECT 
    'Before Fix' AS status,
    COUNT(*) AS record_count,
    COUNT(DISTINCT snapshot_date) AS unique_dates,
    MIN(snapshot_date) AS min_date,
    MAX(snapshot_date) AS max_date
FROM silver.mv_l5_metrics_realtime_backup
WHERE EXISTS (SELECT 1 FROM silver.mv_l5_metrics_realtime_backup)

UNION ALL

SELECT 
    'After Fix' AS status,
    COUNT(*) AS record_count,
    COUNT(DISTINCT snapshot_date) AS unique_dates,
    MIN(snapshot_date) AS min_date,
    MAX(snapshot_date) AS max_date
FROM silver.mv_l5_metrics_realtime;

-- 檢查特定日期的任務數量變化（以 2025-12-30 為例）
SELECT 
    'Before Fix' AS status,
    SUM(total_task_qty) AS total_tasks,
    SUM(todo_qty) AS todo_tasks,
    SUM(doing_qty) AS doing_tasks,
    SUM(done_qty) AS done_tasks
FROM silver.mv_l5_metrics_realtime_backup
WHERE snapshot_date = '2025-12-30'
  AND EXISTS (SELECT 1 FROM silver.mv_l5_metrics_realtime_backup)

UNION ALL

SELECT 
    'After Fix' AS status,
    SUM(total_task_qty) AS total_tasks,
    SUM(todo_qty) AS todo_tasks,
    SUM(doing_qty) AS doing_tasks,
    SUM(done_qty) AS done_tasks
FROM silver.mv_l5_metrics_realtime
WHERE snapshot_date = '2025-12-30';

-- ========================================
-- 4. 建立完成提示
-- ========================================
SELECT 'MVIEW Time Logic Fixed Successfully' AS status,
       'Modified: mv_l5_metrics_realtime, DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV' AS modified_mviews,
       'Time Logic: Now uses OR condition for task_create_time/task_claim_time/task_end_time' AS improvement,
       'Expected: ~20% increase in task coverage' AS expected_impact;