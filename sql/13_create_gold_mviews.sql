-- ========================================
-- Gold 層 Materialized Views
-- ========================================
-- 用途：建立最終的業務指標聚合層，提供給儀表板和報表使用
-- 建立順序：必須在 Silver 層 MView 之後建立
-- 更新方式：Silver 層資料變更時自動觸發更新

-- ========================================
-- 1. 每日 L5 任務完成率快照 MVIEW
-- ========================================
-- 將 Silver 層的即時指標聚合為每日快照，提供歷史趨勢分析

DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;

CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
ENGINE = ReplacingMergeTree()
ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT 
    snapshot_date,  -- 使用 Silver 層的實際日期，而不是 toDate(now())
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
    snapshot_date,  -- 按實際日期分組
    plant,
    factory,
    line,
    vx_type,
    vx_subtype;

-- ========================================
-- 2. 建立查詢視圖（提供業務友好的介面）
-- ========================================

DROP VIEW IF EXISTS gold.vw_daily_l5_completion_summary;

CREATE VIEW gold.vw_daily_l5_completion_summary AS
SELECT 
    snapshot_date,
    plant,
    factory,
    line,
    vx_type,
    vx_subtype,
    
    -- 任務統計
    sum_total_task_qty AS total_tasks,
    sum_todo_qty AS todo_tasks,
    sum_doing_qty AS doing_tasks,
    sum_done_qty AS done_tasks,
    sum_excluded_qty AS excluded_tasks,
    
    -- 百分比
    completion_rate AS completion_pct,
    progress_rate AS progress_pct,
    
    -- 排除統計
    sum_bypass_qty AS bypass_tasks,
    sum_e_prefix_qty AS e_prefix_tasks,
    sum_c_prefix_qty AS c_prefix_tasks,
    sum_q_order_qty AS q_order_tasks,
    sum_r_order_qty AS r_order_tasks,
    
    -- 特殊規則統計
    sum_special_v1_rule_qty AS special_v1_rule_tasks,
    
    _mview_update_time AS last_updated
    
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
ORDER BY snapshot_date DESC, plant, factory, line, vx_type, vx_subtype;

-- ========================================
-- 3. Vx 類型彙總視圖
-- ========================================

DROP VIEW IF EXISTS gold.vw_vx_type_summary;

CREATE VIEW gold.vw_vx_type_summary AS
SELECT 
    snapshot_date,
    vx_type,
    vx_subtype,
    
    -- 彙總統計
    SUM(sum_total_task_qty) AS total_tasks,
    SUM(sum_todo_qty) AS todo_tasks,
    SUM(sum_doing_qty) AS doing_tasks,
    SUM(sum_done_qty) AS done_tasks,
    SUM(sum_excluded_qty) AS excluded_tasks,
    
    -- 完成率
    CASE 
        WHEN SUM(sum_total_task_qty) > 0 
        THEN ROUND(SUM(sum_done_qty) * 100.0 / SUM(sum_total_task_qty), 2)
        ELSE 0.0
    END AS completion_rate,
    
    -- 進行中率
    CASE 
        WHEN SUM(sum_total_task_qty) > 0 
        THEN ROUND((SUM(sum_doing_qty) + SUM(sum_done_qty)) * 100.0 / SUM(sum_total_task_qty), 2)
        ELSE 0.0
    END AS progress_rate,
    
    -- 廠區數量
    COUNT(DISTINCT CONCAT(plant, '|', factory)) AS factory_count,
    COUNT(DISTINCT CONCAT(plant, '|', factory, '|', line)) AS line_count,
    
    MAX(_mview_update_time) AS last_updated
    
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
GROUP BY snapshot_date, vx_type, vx_subtype
ORDER BY snapshot_date DESC, vx_type, vx_subtype;

-- ========================================
-- 4. 廠區彙總視圖
-- ========================================

DROP VIEW IF EXISTS gold.vw_factory_summary;

CREATE VIEW gold.vw_factory_summary AS
SELECT 
    snapshot_date,
    plant,
    factory,
    
    -- 彙總統計
    SUM(sum_total_task_qty) AS total_tasks,
    SUM(sum_todo_qty) AS todo_tasks,
    SUM(sum_doing_qty) AS doing_tasks,
    SUM(sum_done_qty) AS done_tasks,
    SUM(sum_excluded_qty) AS excluded_tasks,
    
    -- 完成率
    CASE 
        WHEN SUM(sum_total_task_qty) > 0 
        THEN ROUND(SUM(sum_done_qty) * 100.0 / SUM(sum_total_task_qty), 2)
        ELSE 0.0
    END AS completion_rate,
    
    -- 進行中率
    CASE 
        WHEN SUM(sum_total_task_qty) > 0 
        THEN ROUND((SUM(sum_doing_qty) + SUM(sum_done_qty)) * 100.0 / SUM(sum_total_task_qty), 2)
        ELSE 0.0
    END AS progress_rate,
    
    -- Vx 類型數量
    COUNT(DISTINCT vx_type) AS vx_type_count,
    COUNT(DISTINCT CONCAT(vx_type, '|', COALESCE(vx_subtype, ''))) AS vx_subtype_count,
    
    -- 產線數量
    COUNT(DISTINCT line) AS line_count,
    
    MAX(_mview_update_time) AS last_updated
    
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
GROUP BY snapshot_date, plant, factory
ORDER BY snapshot_date DESC, plant, factory;

-- ========================================
-- 5. NPE vs MFG 對比視圖（V1 子類型分析）
-- ========================================

DROP VIEW IF EXISTS gold.vw_v1_npe_mfg_comparison;

CREATE VIEW gold.vw_v1_npe_mfg_comparison AS
SELECT 
    snapshot_date,
    plant,
    factory,
    line,
    
    -- V1_NPE 統計
    SUM(CASE WHEN vx_subtype = 'V1_NPE' THEN sum_total_task_qty ELSE 0 END) AS npe_total_tasks,
    SUM(CASE WHEN vx_subtype = 'V1_NPE' THEN sum_done_qty ELSE 0 END) AS npe_done_tasks,
    CASE 
        WHEN SUM(CASE WHEN vx_subtype = 'V1_NPE' THEN sum_total_task_qty ELSE 0 END) > 0 
        THEN ROUND(SUM(CASE WHEN vx_subtype = 'V1_NPE' THEN sum_done_qty ELSE 0 END) * 100.0 / 
                   SUM(CASE WHEN vx_subtype = 'V1_NPE' THEN sum_total_task_qty ELSE 0 END), 2)
        ELSE 0.0
    END AS npe_completion_rate,
    
    -- V1_MFG 統計
    SUM(CASE WHEN vx_subtype = 'V1_MFG' THEN sum_total_task_qty ELSE 0 END) AS mfg_total_tasks,
    SUM(CASE WHEN vx_subtype = 'V1_MFG' THEN sum_done_qty ELSE 0 END) AS mfg_done_tasks,
    CASE 
        WHEN SUM(CASE WHEN vx_subtype = 'V1_MFG' THEN sum_total_task_qty ELSE 0 END) > 0 
        THEN ROUND(SUM(CASE WHEN vx_subtype = 'V1_MFG' THEN sum_done_qty ELSE 0 END) * 100.0 / 
                   SUM(CASE WHEN vx_subtype = 'V1_MFG' THEN sum_total_task_qty ELSE 0 END), 2)
        ELSE 0.0
    END AS mfg_completion_rate,
    
    -- 總計
    SUM(sum_total_task_qty) AS v1_total_tasks,
    SUM(sum_done_qty) AS v1_done_tasks,
    CASE 
        WHEN SUM(sum_total_task_qty) > 0 
        THEN ROUND(SUM(sum_done_qty) * 100.0 / SUM(sum_total_task_qty), 2)
        ELSE 0.0
    END AS v1_completion_rate,
    
    MAX(_mview_update_time) AS last_updated
    
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
WHERE vx_type = 'V1'
GROUP BY snapshot_date, plant, factory, line
HAVING SUM(sum_total_task_qty) > 0
ORDER BY snapshot_date DESC, plant, factory, line;

-- ========================================
-- 建立完成提示
-- ========================================
SELECT 'Gold Layer MViews Created Successfully' AS status,
       'MVIEW tables: DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV' AS created_mviews,
       'Query views: vw_daily_l5_completion_summary, vw_vx_type_summary, vw_factory_summary, vw_v1_npe_mfg_comparison' AS created_views,
       'Next: Verify data population and NPE logic' AS next_step;