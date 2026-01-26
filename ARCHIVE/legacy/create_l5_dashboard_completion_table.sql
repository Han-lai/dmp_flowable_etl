-- ========================================
-- L5 任務執行完成度 Dashboard 彙總表
-- ========================================
-- 用途：為 L5 任務執行完成度 Dashboard 提供完整的彙總表
-- 支援：上方圖表（Todo/Doing/Done 分布 + 完成率折線）+ 下方明細表
-- 時間層級：Day / Week / Month 動態展開
-- 維度：製造五階 + Vx 類型範圍

DROP TABLE IF EXISTS gold.L5_DASHBOARD_COMPLETION_SUMMARY_MV;

CREATE MATERIALIZED VIEW gold.L5_DASHBOARD_COMPLETION_SUMMARY_MV
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (snapshot_date, time_level, time_value, flow_team, region, plant, factory, line, vx_scope)
SETTINGS allow_nullable_key = 1
POPULATE
AS
WITH base_data AS (
    SELECT 
        snapshot_date,
        
        -- 製造與流程維度（必須存在）
        CASE 
            WHEN vx_type IN ('V1', 'V2', 'V3') THEN CONCAT(vx_type, '+V1+V2+V3')
            ELSE 'V1+V2+V3'
        END AS flow_team,                                    -- 流程團隊（如：V1+V2+V3）
        
        COALESCE(region_code, 'Unknown') AS region,          -- 地區（如：CNE）
        COALESCE(plant_code, 'Unknown') AS plant,            -- 製造廠區（如：WJ2）
        COALESCE(factory_code, 'Unknown') AS factory,        -- 製造產品廠（如：NBU）
        COALESCE(line_code, '') AS line,                     -- 線體（如：E5）- 可為空
        
        -- Vx 類型範圍
        CASE 
            WHEN vx_type = 'V1' THEN 'V1'
            WHEN vx_type = 'V2' THEN 'V2'
            WHEN vx_type = 'V3' THEN 'V3'
            ELSE 'V1+V2+V3'
        END AS vx_scope,                                     -- 任務類型範圍（V1 / V2 / V3 / V1+V2+V3）
        
        -- 任務狀態數量
        sum_total_task_qty AS total_task,
        sum_todo_qty AS todo_task,
        sum_doing_qty AS doing_task,
        sum_done_qty AS done_task,
        
        -- 組合狀態
        (sum_doing_qty + sum_done_qty) AS doing_done_task,   -- Doing+Done
        (sum_todo_qty + sum_doing_qty) AS todo_doing_acc_task -- Todo+Doing(Acc)
        
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
    WHERE sum_total_task_qty > 0  -- 排除無任務記錄
),

-- 日彙總
daily_summary AS (
    SELECT 
        snapshot_date,
        'Day' AS time_level,
        toString(snapshot_date) AS time_value,
        flow_team,
        region,
        plant,
        factory,
        line,
        vx_scope,
        
        -- 任務狀態彙總
        SUM(total_task) AS total_task_qty,
        SUM(todo_task) AS todo_task_qty,
        SUM(doing_task) AS doing_task_qty,
        SUM(done_task) AS done_task_qty,
        SUM(doing_done_task) AS doing_done_task_qty,
        SUM(todo_doing_acc_task) AS todo_doing_acc_task_qty
        
    FROM base_data
    GROUP BY snapshot_date, flow_team, region, plant, factory, line, vx_scope
),

-- 週彙總
weekly_summary AS (
    SELECT 
        snapshot_date,
        'Week' AS time_level,
        CONCAT('W', toString(toISOWeek(snapshot_date))) AS time_value,
        flow_team,
        region,
        plant,
        factory,
        line,
        vx_scope,
        
        -- 任務狀態彙總
        SUM(total_task) AS total_task_qty,
        SUM(todo_task) AS todo_task_qty,
        SUM(doing_task) AS doing_task_qty,
        SUM(done_task) AS done_task_qty,
        SUM(doing_done_task) AS doing_done_task_qty,
        SUM(todo_doing_acc_task) AS todo_doing_acc_task_qty
        
    FROM base_data
    GROUP BY snapshot_date, toISOWeek(snapshot_date), flow_team, region, plant, factory, line, vx_scope
),

-- 月彙總
monthly_summary AS (
    SELECT 
        snapshot_date,
        'Month' AS time_level,
        formatDateTime(snapshot_date, '%b') AS time_value,  -- Dec, Jan, Feb
        flow_team,
        region,
        plant,
        factory,
        line,
        vx_scope,
        
        -- 任務狀態彙總
        SUM(total_task) AS total_task_qty,
        SUM(todo_task) AS todo_task_qty,
        SUM(doing_task) AS doing_task_qty,
        SUM(done_task) AS done_task_qty,
        SUM(doing_done_task) AS doing_done_task_qty,
        SUM(todo_doing_acc_task) AS todo_doing_acc_task_qty
        
    FROM base_data
    GROUP BY snapshot_date, toYYYYMM(snapshot_date), flow_team, region, plant, factory, line, vx_scope
)

-- 合併所有時間層級
SELECT 
    snapshot_date,
    time_level,
    time_value,
    flow_team,
    region,
    plant,
    factory,
    line,
    vx_scope,
    
    -- ========================================
    -- 任務狀態數量欄位
    -- ========================================
    total_task_qty,
    todo_task_qty,
    doing_task_qty,
    done_task_qty,
    doing_done_task_qty,
    todo_doing_acc_task_qty,
    
    -- ========================================
    -- 任務狀態百分比欄位
    -- ========================================
    -- Todo 比例
    CASE 
        WHEN total_task_qty > 0 
        THEN ROUND(todo_task_qty * 100.0 / total_task_qty, 2)
        ELSE 0.0
    END AS todo_task_pct,
    
    -- Doing 比例
    CASE 
        WHEN total_task_qty > 0 
        THEN ROUND(doing_task_qty * 100.0 / total_task_qty, 2)
        ELSE 0.0
    END AS doing_task_pct,
    
    -- Done 比例
    CASE 
        WHEN total_task_qty > 0 
        THEN ROUND(done_task_qty * 100.0 / total_task_qty, 2)
        ELSE 0.0
    END AS done_task_pct,
    
    -- Doing+Done 比例
    CASE 
        WHEN total_task_qty > 0 
        THEN ROUND(doing_done_task_qty * 100.0 / total_task_qty, 2)
        ELSE 0.0
    END AS doing_done_task_pct,
    
    -- Todo+Doing(Acc) 比例
    CASE 
        WHEN total_task_qty > 0 
        THEN ROUND(todo_doing_acc_task_qty * 100.0 / total_task_qty, 2)
        ELSE 0.0
    END AS todo_doing_acc_task_pct,
    
    -- Metadata
    now64(3) AS _mview_update_time
    
FROM (
    SELECT * FROM daily_summary
    UNION ALL
    SELECT * FROM weekly_summary
    UNION ALL
    SELECT * FROM monthly_summary
)
ORDER BY snapshot_date DESC, time_level, flow_team, region, plant, factory, line, vx_scope;

-- ========================================
-- 建立 Dashboard 專用查詢視圖
-- ========================================

DROP VIEW IF EXISTS gold.vw_l5_dashboard_completion;

CREATE VIEW gold.vw_l5_dashboard_completion AS
SELECT 
    snapshot_date,
    time_level,
    time_value,
    
    -- 維度欄位
    flow_team,
    region,
    plant,
    factory,
    line,
    vx_scope,
    
    -- 組合維度（用於分組顯示）
    CONCAT(region, '-', plant, '-', factory) AS location_path,
    CASE 
        WHEN line != '' THEN CONCAT(region, '-', plant, '-', factory, '-', line)
        ELSE CONCAT(region, '-', plant, '-', factory)
    END AS full_location_path,
    
    -- 任務狀態數量
    total_task_qty,
    todo_task_qty,
    doing_task_qty,
    done_task_qty,
    doing_done_task_qty,
    todo_doing_acc_task_qty,
    
    -- 任務狀態百分比
    todo_task_pct,
    doing_task_pct,
    done_task_pct,
    doing_done_task_pct,
    todo_doing_acc_task_pct,
    
    -- Dashboard 圖表專用欄位
    done_task_pct AS completion_rate,           -- 完成率折線圖
    doing_done_task_pct AS progress_rate,       -- 執行率折線圖
    todo_doing_acc_task_pct AS accumulation_rate, -- 累積率折線圖
    
    -- 驗證欄位（確保數據正確性）
    CASE 
        WHEN total_task_qty > 0 
        THEN ROUND((todo_task_qty + doing_task_qty + done_task_qty) * 100.0 / total_task_qty, 2)
        ELSE 0.0
    END AS total_coverage_pct,  -- 應該等於 100%
    
    _mview_update_time AS last_updated
    
FROM gold.L5_DASHBOARD_COMPLETION_SUMMARY_MV FINAL
ORDER BY snapshot_date DESC, time_level, flow_team, region, plant, factory, line, vx_scope;

-- ========================================
-- 建立 Dashboard 圖表專用視圖（上方圖表）
-- ========================================

DROP VIEW IF EXISTS gold.vw_l5_dashboard_charts;

CREATE VIEW gold.vw_l5_dashboard_charts AS
SELECT 
    snapshot_date,
    time_level,
    time_value,
    vx_scope,
    
    -- 聚合所有維度的任務狀態
    SUM(total_task_qty) AS total_tasks,
    SUM(todo_task_qty) AS todo_tasks,
    SUM(doing_task_qty) AS doing_tasks,
    SUM(done_task_qty) AS done_tasks,
    SUM(doing_done_task_qty) AS doing_done_tasks,
    SUM(todo_doing_acc_task_qty) AS todo_doing_acc_tasks,
    
    -- 整體比例（用於圖表）
    CASE 
        WHEN SUM(total_task_qty) > 0 
        THEN ROUND(SUM(todo_task_qty) * 100.0 / SUM(total_task_qty), 2)
        ELSE 0.0
    END AS overall_todo_pct,
    
    CASE 
        WHEN SUM(total_task_qty) > 0 
        THEN ROUND(SUM(doing_task_qty) * 100.0 / SUM(total_task_qty), 2)
        ELSE 0.0
    END AS overall_doing_pct,
    
    CASE 
        WHEN SUM(total_task_qty) > 0 
        THEN ROUND(SUM(done_task_qty) * 100.0 / SUM(total_task_qty), 2)
        ELSE 0.0
    END AS overall_done_pct,
    
    CASE 
        WHEN SUM(total_task_qty) > 0 
        THEN ROUND(SUM(doing_done_task_qty) * 100.0 / SUM(total_task_qty), 2)
        ELSE 0.0
    END AS overall_progress_pct,
    
    CASE 
        WHEN SUM(total_task_qty) > 0 
        THEN ROUND(SUM(todo_doing_acc_task_qty) * 100.0 / SUM(total_task_qty), 2)
        ELSE 0.0
    END AS overall_accumulation_pct,
    
    MAX(last_updated) AS last_updated
    
FROM gold.vw_l5_dashboard_completion
GROUP BY snapshot_date, time_level, time_value, vx_scope
ORDER BY snapshot_date DESC, time_level, vx_scope;

-- ========================================
-- 建立完成提示
-- ========================================
SELECT 'L5 Dashboard Completion Tables Created Successfully' AS status,
       'Main table: gold.L5_DASHBOARD_COMPLETION_SUMMARY_MV' AS main_table,
       'Detail view: gold.vw_l5_dashboard_completion' AS detail_view,
       'Chart view: gold.vw_l5_dashboard_charts' AS chart_view,
       'Ready for Dashboard integration' AS next_step;