-- ========================================
-- Gold 層 L5 任務儀表板彙總表
-- ========================================
-- 用途：為 Superset 儀表板提供標準化的 L5 任務指標彙總表
-- 更新頻率：每日自動更新
-- Schema：符合儀表板需求的標準化結構

DROP TABLE IF EXISTS gold.L5_DASHBOARD_SUMMARY_MV;

CREATE MATERIALIZED VIEW gold.L5_DASHBOARD_SUMMARY_MV
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (snapshot_date, region, plant, factory, line, vx_type)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT
    -- ========================================
    -- 主鍵維度欄位
    -- ========================================
    snapshot_date,                                    -- 快照日期（每日）
    COALESCE(region_code, '') AS region,            -- 地區（製造五階）
    COALESCE(plant_code, '') AS plant,              -- 廠別
    COALESCE(factory_code, '') AS factory,          -- 工廠
    COALESCE(line_code, '') AS line,                -- 線體
    vx_type,                                         -- V1 / V2 / V3
    
    -- ========================================
    -- 任務狀態彙總欄位
    -- ========================================
    sum_total_task_qty AS total_task,               -- 任務總數
    sum_todo_qty AS todo_cnt,                       -- Todo 數量
    sum_doing_qty AS doing_cnt,                     -- Doing 數量
    sum_done_qty AS done_cnt,                       -- Done 數量
    
    -- 組合統計欄位
    (sum_doing_qty + sum_done_qty) AS doing_done_cnt,           -- Doing + Done
    (sum_todo_qty + sum_doing_qty) AS todo_doing_acc_cnt,       -- Todo + Doing
    
    -- ========================================
    -- 比例欄位（需一併產出）
    -- ========================================
    -- todo_rate = todo_cnt / total_task
    CASE 
        WHEN sum_total_task_qty > 0 
        THEN ROUND(sum_todo_qty * 100.0 / sum_total_task_qty, 2)
        ELSE 0.0
    END AS todo_rate,
    
    -- doing_rate = doing_cnt / total_task
    CASE 
        WHEN sum_total_task_qty > 0 
        THEN ROUND(sum_doing_qty * 100.0 / sum_total_task_qty, 2)
        ELSE 0.0
    END AS doing_rate,
    
    -- done_rate = done_cnt / total_task
    CASE 
        WHEN sum_total_task_qty > 0 
        THEN ROUND(sum_done_qty * 100.0 / sum_total_task_qty, 2)
        ELSE 0.0
    END AS done_rate,
    
    -- doing_done_rate = (doing_cnt + done_cnt) / total_task
    CASE 
        WHEN sum_total_task_qty > 0 
        THEN ROUND((sum_doing_qty + sum_done_qty) * 100.0 / sum_total_task_qty, 2)
        ELSE 0.0
    END AS doing_done_rate,
    
    -- todo_doing_acc_rate = (todo_cnt + doing_cnt) / total_task
    CASE 
        WHEN sum_total_task_qty > 0 
        THEN ROUND((sum_todo_qty + sum_doing_qty) * 100.0 / sum_total_task_qty, 2)
        ELSE 0.0
    END AS todo_doing_acc_rate,
    
    -- ========================================
    -- 輔助欄位（用於分析）
    -- ========================================
    -- 維度資料來源統計
    sum_mdm_primary_qty AS mdm_primary_tasks,       -- MDM 主來源任務數
    sum_flowable_fallback_qty AS flowable_fallback_tasks,  -- Flowable 輔助來源任務數
    sum_no_dimension_qty AS no_dimension_tasks,     -- 無維度任務數
    
    -- 排除統計
    sum_bypass_qty AS bypass_tasks,                 -- 旁路任務數
    
    -- 完整維度名稱（用於顯示）
    COALESCE(region_name, '') AS region_name,
    COALESCE(plant_name, '') AS plant_name,
    COALESCE(factory_name, '') AS factory_name,
    COALESCE(line_name, '') AS line_name,
    
    -- 組合維度路徑
    CONCAT(
        COALESCE(region_code, ''), '>', 
        COALESCE(plant_code, ''), '>', 
        COALESCE(factory_code, ''), '>', 
        COALESCE(line_code, '')
    ) AS dimension_path,
    
    -- Metadata
    now64(3) AS _mview_update_time
    
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
WHERE sum_total_task_qty > 0  -- 只包含有任務的記錄
ORDER BY snapshot_date DESC, region, plant, factory, line, vx_type;

-- ========================================
-- 建立查詢視圖（提供業務友好的介面）
-- ========================================

DROP VIEW IF EXISTS gold.vw_l5_dashboard_summary;

CREATE VIEW gold.vw_l5_dashboard_summary AS
SELECT 
    -- 主鍵維度
    snapshot_date,
    region,
    plant,
    factory,
    line,
    vx_type,
    
    -- 任務狀態彙總
    total_task,
    todo_cnt,
    doing_cnt,
    done_cnt,
    doing_done_cnt,
    todo_doing_acc_cnt,
    
    -- 比例欄位（百分比格式）
    todo_rate,
    doing_rate,
    done_rate,
    doing_done_rate,
    todo_doing_acc_rate,
    
    -- 輔助分析欄位
    mdm_primary_tasks,
    flowable_fallback_tasks,
    no_dimension_tasks,
    bypass_tasks,
    
    -- 維度名稱
    region_name,
    plant_name,
    factory_name,
    line_name,
    dimension_path,
    
    -- 計算欄位（用於驗證）
    CASE 
        WHEN total_task > 0 
        THEN ROUND((todo_cnt + doing_cnt + done_cnt) * 100.0 / total_task, 2)
        ELSE 0.0
    END AS total_coverage_rate,  -- 總覆蓋率驗證
    
    _mview_update_time AS last_updated
    
FROM gold.L5_DASHBOARD_SUMMARY_MV FINAL
ORDER BY snapshot_date DESC, region, plant, factory, line, vx_type;

-- ========================================
-- 建立 Superset 專用的平面化視圖
-- ========================================

DROP VIEW IF EXISTS gold.vw_superset_l5_summary;

CREATE VIEW gold.vw_superset_l5_summary AS
SELECT 
    -- 時間維度
    snapshot_date,
    toYear(snapshot_date) AS snapshot_year,
    toMonth(snapshot_date) AS snapshot_month,
    toDayOfMonth(snapshot_date) AS snapshot_day,
    toISOWeek(snapshot_date) AS snapshot_week,
    
    -- 業務維度
    region,
    plant,
    factory,
    line,
    vx_type,
    
    -- 維度名稱（用於顯示）
    region_name,
    plant_name,
    factory_name,
    line_name,
    
    -- 組合維度
    CONCAT(region, '-', plant) AS region_plant,
    CONCAT(plant, '-', factory) AS plant_factory,
    CONCAT(factory, '-', line) AS factory_line,
    CONCAT(vx_type, '-', plant) AS vx_plant,
    dimension_path,
    
    -- 任務數量指標
    total_task,
    todo_cnt,
    doing_cnt,
    done_cnt,
    doing_done_cnt,
    todo_doing_acc_cnt,
    
    -- 比例指標（百分比）
    todo_rate,
    doing_rate,
    done_rate,
    doing_done_rate,
    todo_doing_acc_rate,
    
    -- 輔助指標
    mdm_primary_tasks,
    flowable_fallback_tasks,
    no_dimension_tasks,
    bypass_tasks,
    
    -- 分析指標
    total_coverage_rate,
    
    -- 分類標籤（用於篩選和分組）
    CASE 
        WHEN done_rate >= 80 THEN 'High Performance (>=80%)'
        WHEN done_rate >= 60 THEN 'Good Performance (60-79%)'
        WHEN done_rate >= 40 THEN 'Average Performance (40-59%)'
        WHEN done_rate > 0 THEN 'Low Performance (1-39%)'
        ELSE 'No Completion (0%)'
    END AS performance_level,
    
    CASE 
        WHEN total_task >= 1000 THEN 'High Volume (>=1000)'
        WHEN total_task >= 500 THEN 'Medium Volume (500-999)'
        WHEN total_task >= 100 THEN 'Low Volume (100-499)'
        WHEN total_task > 0 THEN 'Very Low Volume (1-99)'
        ELSE 'No Tasks'
    END AS volume_level,
    
    -- Metadata
    last_updated
    
FROM gold.vw_l5_dashboard_summary
ORDER BY snapshot_date DESC, region, plant, factory, line, vx_type;

-- ========================================
-- 建立完成提示
-- ========================================
SELECT 'L5 Dashboard Summary Tables Created Successfully' AS status,
       'Main table: gold.L5_DASHBOARD_SUMMARY_MV' AS main_table,
       'Business view: gold.vw_l5_dashboard_summary' AS business_view,
       'Superset view: gold.vw_superset_l5_summary' AS superset_view,
       'Ready for Superset integration' AS next_step;