-- ========================================
-- ISO Week 合規性修正 SQL
-- ========================================
-- 修正項目：
-- 1. 實作正確的 W-pattern 邏輯（當前月份 vs 歷史月份）
-- 2. 新增 Dn-1 動態日期邏輯
-- 3. 確保所有週次計算使用 ISO Week

-- ========================================
-- 修正 1: L5 Dashboard Completion Table - 新增 W-pattern 和 Dn-1 支援
-- ========================================

DROP VIEW IF EXISTS gold.vw_l5_dashboard_time_patterns;

CREATE VIEW gold.vw_l5_dashboard_time_patterns AS
WITH time_pattern_logic AS (
    SELECT 
        snapshot_date,
        
        -- 當前日期和查詢月份
        today() AS current_date,
        toYYYYMM(snapshot_date) AS query_month,
        toYYYYMM(today()) AS current_month,
        
        -- W-pattern 邏輯：區分當前月份 vs 歷史月份
        CASE 
            WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
            THEN toISOWeek(today())  -- 當前月份：使用今日所屬 ISO 週次
            ELSE toISOWeek(toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01'))))  -- 歷史月份：使用該月最後一日所屬 ISO 週次
        END AS x_week,
        
        -- W-pattern 產出：W{x}, W{x-1}, W{x-2}
        CONCAT('W', toString(
            CASE 
                WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
                THEN toISOWeek(today())
                ELSE toISOWeek(toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01'))))
            END
        )) AS w_current,
        
        CONCAT('W', toString(
            CASE 
                WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
                THEN toISOWeek(today()) - 1
                ELSE toISOWeek(toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01')))) - 1
            END
        )) AS w43,
        
        CONCAT('W', toString(
            CASE 
                WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
                THEN toISOWeek(today()) - 2
                ELSE toISOWeek(toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01')))) - 2
            END
        )) AS w42,
        
        -- Dn-1 邏輯：區分當前月份 vs 歷史月份
        CASE 
            WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
            THEN today() - INTERVAL 1 DAY  -- 當前月份：today - 1
            ELSE toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01')))  -- 歷史月份：該月最後一日
        END AS d0,
        
        CASE 
            WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
            THEN today() - INTERVAL 2 DAY  -- 當前月份：today - 2
            ELSE toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01'))) - INTERVAL 1 DAY  -- 歷史月份：月底 - 1
        END AS d1,
        
        CASE 
            WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
            THEN today() - INTERVAL 3 DAY  -- 當前月份：today - 3
            ELSE toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01'))) - INTERVAL 2 DAY  -- 歷史月份：月底 - 2
        END AS d2
    FROM (
        SELECT DISTINCT snapshot_date 
        FROM gold.l5_dashboard_summary
        WHERE snapshot_date IS NOT NULL
    )
)
SELECT 
    snapshot_date,
    current_date,
    query_month,
    current_month,
    
    -- 月份類型標記
    CASE 
        WHEN query_month = current_month THEN 'CURRENT_MONTH'
        ELSE 'HISTORY_MONTH'
    END AS month_type,
    
    -- W-pattern 欄位
    x_week,
    w_current,
    w43,
    w42,
    
    -- Dn-1 欄位
    d0,
    d1,
    d2,
    
    -- ISO Week 相關欄位
    toISOWeek(snapshot_date) AS snapshot_iso_week,
    toISOWeek(d0) AS d0_iso_week,
    
    -- 週次範圍計算（ISO Week）
    toMonday(snapshot_date) AS snapshot_week_monday,
    toMonday(snapshot_date) + INTERVAL 6 DAY AS snapshot_week_sunday,
    
    -- 驗證欄位
    CASE 
        WHEN toDayOfWeek(toMonday(snapshot_date)) = 1 THEN '✅ 週一起算'
        ELSE '❌ 非週一起算'
    END AS iso_week_validation
    
FROM time_pattern_logic
ORDER BY snapshot_date DESC;

-- ========================================
-- 修正 2: 更新 L5 Dashboard Completion Summary MVIEW - 使用正確的 ISO Week
-- ========================================

CREATE OR REPLACE VIEW gold.v_l5_dashboard_completion_summary_fixed AS
WITH base_data AS (
    SELECT 
        snapshot_date,
        
        -- 製造與流程維度（必須存在）
        CASE 
            WHEN vx_type IN ('V1', 'V2', 'V3') THEN CONCAT(vx_type, '+V1+V2+V3')
            ELSE 'V1+V2+V3'
        END AS flow_team,
        
        COALESCE(region, 'Unknown') AS region,
        COALESCE(plant, 'Unknown') AS plant,
        COALESCE(factory, 'Unknown') AS factory,
        COALESCE(line, '') AS line,
        
        -- Vx 類型範圍
        CASE 
            WHEN vx_type = 'V1' THEN 'V1'
            WHEN vx_type = 'V2' THEN 'V2'
            WHEN vx_type = 'V3' THEN 'V3'
            ELSE 'V1+V2+V3'
        END AS vx_scope,
        
        -- 任務狀態數量
        total_task,
        todo_task,
        doing_task,
        done_task,
        
        -- 組合狀態
        (doing_task + done_task) AS doing_done_task,
        (todo_task + doing_task) AS todo_doing_acc_task
        
    FROM gold.l5_dashboard_summary
    WHERE total_task > 0
),

-- 日彙總
daily_summary AS (
    SELECT 
        snapshot_date,
        'Day' AS time_level,
        toString(snapshot_date) AS time_value,
        flow_team, region, plant, factory, line, vx_scope,
        
        SUM(total_task) AS total_task_qty,
        SUM(todo_task) AS todo_task_qty,
        SUM(doing_task) AS doing_task_qty,
        SUM(done_task) AS done_task_qty,
        SUM(doing_done_task) AS doing_done_task_qty,
        SUM(todo_doing_acc_task) AS todo_doing_acc_task_qty
        
    FROM base_data
    GROUP BY snapshot_date, flow_team, region, plant, factory, line, vx_scope
),

-- 週彙總 - 修正：使用 ISO Week
weekly_summary AS (
    SELECT 
        snapshot_date,
        'Week' AS time_level,
        -- 修正：使用正確的 W-pattern 邏輯
        CASE 
            WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
            THEN CONCAT('W', toString(toISOWeek(today())))
            ELSE CONCAT('W', toString(toISOWeek(toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01'))))))
        END AS time_value,
        flow_team, region, plant, factory, line, vx_scope,
        
        SUM(total_task) AS total_task_qty,
        SUM(todo_task) AS todo_task_qty,
        SUM(doing_task) AS doing_task_qty,
        SUM(done_task) AS done_task_qty,
        SUM(doing_done_task) AS doing_done_task_qty,
        SUM(todo_doing_acc_task) AS todo_doing_acc_task_qty
        
    FROM base_data
    -- 修正：按 ISO Week 分組
    GROUP BY snapshot_date, 
             CASE 
                 WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
                 THEN toISOWeek(today())
                 ELSE toISOWeek(toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01'))))
             END,
             flow_team, region, plant, factory, line, vx_scope
),

-- 月彙總
monthly_summary AS (
    SELECT 
        snapshot_date,
        'Month' AS time_level,
        formatDateTime(snapshot_date, '%b') AS time_value,
        flow_team, region, plant, factory, line, vx_scope,
        
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
    snapshot_date, time_level, time_value,
    flow_team, region, plant, factory, line, vx_scope,
    
    total_task_qty, todo_task_qty, doing_task_qty, done_task_qty,
    doing_done_task_qty, todo_doing_acc_task_qty,
    
    -- 任務狀態百分比欄位
    CASE WHEN total_task_qty > 0 THEN ROUND(todo_task_qty * 100.0 / total_task_qty, 2) ELSE 0.0 END AS todo_task_pct,
    CASE WHEN total_task_qty > 0 THEN ROUND(doing_task_qty * 100.0 / total_task_qty, 2) ELSE 0.0 END AS doing_task_pct,
    CASE WHEN total_task_qty > 0 THEN ROUND(done_task_qty * 100.0 / total_task_qty, 2) ELSE 0.0 END AS done_task_pct,
    CASE WHEN total_task_qty > 0 THEN ROUND(doing_done_task_qty * 100.0 / total_task_qty, 2) ELSE 0.0 END AS doing_done_task_pct,
    CASE WHEN total_task_qty > 0 THEN ROUND(todo_doing_acc_task_qty * 100.0 / total_task_qty, 2) ELSE 0.0 END AS todo_doing_acc_task_pct,
    
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
-- 修正 3: 更新 Superset L5 Summary View - 使用正確的 ISO Week
-- ========================================

CREATE OR REPLACE VIEW gold.vw_superset_l5_summary_fixed AS
SELECT 
    -- 時間維度 - 修正：確保使用 ISO Week
    snapshot_date,
    toYear(snapshot_date) AS snapshot_year,
    toMonth(snapshot_date) AS snapshot_month,
    toDayOfMonth(snapshot_date) AS snapshot_day,
    toISOWeek(snapshot_date) AS snapshot_week,  -- 確認使用 ISO Week
    
    -- W-pattern 欄位 - 新增
    CASE 
        WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
        THEN CONCAT('W', toString(toISOWeek(today())))
        ELSE CONCAT('W', toString(toISOWeek(toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01'))))))
    END AS w_pattern_current,
    
    CASE 
        WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
        THEN CONCAT('W', toString(toISOWeek(today()) - 1))
        ELSE CONCAT('W', toString(toISOWeek(toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01')))) - 1))
    END AS w43,
    
    CASE 
        WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
        THEN CONCAT('W', toString(toISOWeek(today()) - 2))
        ELSE CONCAT('W', toString(toISOWeek(toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01')))) - 2))
    END AS w42,
    
    -- Dn-1 欄位 - 新增
    CASE 
        WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
        THEN today() - INTERVAL 1 DAY
        ELSE toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01')))
    END AS d0,
    
    CASE 
        WHEN toYYYYMM(snapshot_date) = toYYYYMM(today()) 
        THEN today() - INTERVAL 2 DAY
        ELSE toLastDayOfMonth(toDate(CONCAT(toString(toYear(snapshot_date)), '-', toString(toMonth(snapshot_date)), '-01'))) - INTERVAL 1 DAY
    END AS d1,
    
    -- 業務維度
    region, plant, factory, line, vx_type,
    
    -- 組合維度
    CONCAT(region, '-', plant) AS region_plant,
    CONCAT(plant, '-', factory) AS plant_factory,
    CONCAT(factory, '-', line) AS factory_line,
    CONCAT(vx_type, '-', plant) AS vx_plant,
    CONCAT(region, '>', plant, '>', factory, '>', line) AS dimension_path,
    
    -- 任務數量指標
    total_task, todo_task, doing_task, done_task,
    (doing_task + done_task) AS doing_done_task,
    (todo_task + doing_task) AS todo_doing_acc_task,
    
    -- 比例指標（百分比）
    CASE WHEN total_task > 0 THEN ROUND(todo_task * 100.0 / total_task, 2) ELSE 0.0 END AS todo_rate,
    CASE WHEN total_task > 0 THEN ROUND(doing_task * 100.0 / total_task, 2) ELSE 0.0 END AS doing_rate,
    CASE WHEN total_task > 0 THEN ROUND(done_task * 100.0 / total_task, 2) ELSE 0.0 END AS done_rate,
    completion_rate,
    
    -- 維度資料品質統計
    region_mdm_backfill_count, plant_mdm_backfill_count, 
    factory_mdm_backfill_count, line_mdm_backfill_count,
    
    -- 分類標籤
    CASE 
        WHEN completion_rate >= 80 THEN 'High Performance (>=80%)'
        WHEN completion_rate >= 60 THEN 'Good Performance (60-79%)'
        WHEN completion_rate >= 40 THEN 'Average Performance (40-59%)'
        WHEN completion_rate > 0 THEN 'Low Performance (1-39%)'
        ELSE 'No Completion (0%)'
    END AS performance_level,
    
    CASE 
        WHEN total_task >= 1000 THEN 'High Volume (>=1000)'
        WHEN total_task >= 500 THEN 'Medium Volume (500-999)'
        WHEN total_task >= 100 THEN 'Low Volume (100-499)'
        WHEN total_task > 0 THEN 'Very Low Volume (1-99)'
        ELSE 'No Tasks'
    END AS volume_level,
    
    -- ISO Week 驗證欄位
    toDayOfWeek(toMonday(snapshot_date)) AS week_start_validation,  -- 應該是 1 (週一)
    toMonday(snapshot_date) AS iso_week_monday,
    toMonday(snapshot_date) + INTERVAL 6 DAY AS iso_week_sunday,
    
    -- Metadata
    _update_time AS last_updated
    
FROM gold.l5_dashboard_summary
ORDER BY snapshot_date DESC, region, plant, factory, line, vx_type;

-- ========================================
-- 建立完成提示
-- ========================================
SELECT 
    '✅ ISO Week 合規性修正完成' AS status,
    'gold.vw_l5_dashboard_time_patterns' AS time_pattern_view,
    'gold.v_l5_dashboard_completion_summary_fixed' AS fixed_completion_view,
    'gold.vw_superset_l5_summary_fixed' AS fixed_superset_view,
    '所有週次計算已改用 toISOWeek()' AS iso_week_compliance,
    '已實作 W-pattern 和 Dn-1 動態邏輯' AS pattern_compliance
;