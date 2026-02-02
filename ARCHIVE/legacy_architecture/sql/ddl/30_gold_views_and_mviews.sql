-- ========================================
-- Gold 層 Views 和 Tables - 使用 Silver 層補齊維度
-- 規則：完全信任 Silver 層已補齊完成的欄位
-- ========================================

-- ========================================
-- 1. L5 儀表板摘要表
-- ========================================

DROP TABLE IF EXISTS gold.l5_dashboard_summary;

CREATE TABLE gold.l5_dashboard_summary
(
    snapshot_date Date,
    vx_type LowCardinality(String),
    
    -- 完整五階維度（使用 Silver 層補齊結果）
    region String,
    plant String,
    factory String,
    line String,
    
    -- 維度資料來源追蹤
    region_source String,
    plant_source String,
    factory_source String,
    line_source String,
    dimension_source String,
    
    -- 任務統計
    total_task UInt32,
    todo_task UInt32,
    doing_task UInt32,
    done_task UInt32,
    
    -- 完成率
    completion_rate Decimal(5, 2),
    
    -- 維度資料品質統計
    region_mdm_backfill_count UInt32,
    plant_mdm_backfill_count UInt32,
    factory_mdm_backfill_count UInt32,
    line_mdm_backfill_count UInt32,
    
    -- Metadata
    _version UInt64,
    _update_time DateTime64(3)
)
ENGINE = ReplacingMergeTree(_version)
ORDER BY (snapshot_date, vx_type, region, plant, factory, line)
SETTINGS allow_nullable_key = 1;

-- ========================================
-- 2. L5 儀表板摘要表 - 填入資料的 View
-- ========================================

CREATE OR REPLACE VIEW gold.v_l5_dashboard_summary_populate AS
SELECT
    task_create_date AS snapshot_date,
    vx_type,
    
    -- 使用 Silver 層補齊後的完整五階維度
    region,
    plant,
    factory,
    line,
    
    -- 維度資料來源追蹤
    region_source,
    plant_source,
    factory_source,
    line_source,
    dimension_source,
    
    -- 任務統計
    COUNT(*) AS total_task,
    countIf(task_status = 'TODO') AS todo_task,
    countIf(task_status = 'DOING') AS doing_task,
    countIf(task_status = 'DONE') AS done_task,
    
    -- 完成率
    CASE 
        WHEN COUNT(*) > 0 
        THEN countIf(task_status = 'DONE') * 100.0 / COUNT(*)
        ELSE 0
    END AS completion_rate,
    
    -- 維度資料品質統計
    countIf(region_source = 'MDM') AS region_mdm_backfill_count,
    countIf(plant_source = 'MDM') AS plant_mdm_backfill_count,
    countIf(factory_source = 'MDM') AS factory_mdm_backfill_count,
    countIf(line_source = 'MDM') AS line_mdm_backfill_count,
    
    -- Metadata
    1 AS _version,
    now64(3) AS _update_time

FROM silver.mv_fact_task_vx_attribution_mdm
WHERE is_excluded = 0
  AND task_create_date >= '2025-01-01'  -- 限制資料範圍
GROUP BY 
    task_create_date, vx_type, region, plant, factory, line,
    region_source, plant_source, factory_source, line_source, dimension_source;

-- ========================================
-- 3. 初始化 L5 儀表板摘要表資料
-- ========================================

-- 清空並重新填入資料
TRUNCATE TABLE gold.l5_dashboard_summary;

INSERT INTO gold.l5_dashboard_summary
SELECT * FROM gold.v_l5_dashboard_summary_populate;

SELECT 'Gold layer views and tables created successfully' AS status;