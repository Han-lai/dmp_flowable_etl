-- ========================================
-- 更新 Gold 層維度補齊邏輯
-- 規則：完全信任 Silver 層已補齊完成的欄位
-- ========================================

-- ========================================
-- 1. 更新 Gold 層任務完成快照表
-- ========================================

-- 備份現有表
DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_BACKUP;
CREATE TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_BACKUP
ENGINE = MergeTree()
ORDER BY (snapshot_date, vx_type, plant, factory)
AS SELECT * FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT;

-- 重建表，使用 Silver 層的補齊維度
DROP TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT;

CREATE TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
(
    snapshot_date Date,
    vx_type LowCardinality(String),
    vx_subtype String,
    
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
    
    -- 時間維度
    time_period_type LowCardinality(String),
    time_period_value String,
    
    -- 任務統計
    total_task_qty UInt32,
    todo_qty UInt32,
    doing_qty UInt32,
    done_qty UInt32,
    doing_done_qty UInt32,
    todo_doing_acc_qty UInt32,
    
    -- 百分比統計
    todo_pct Decimal(5, 2),
    doing_pct Decimal(5, 2),
    done_pct Decimal(5, 2),
    doing_done_pct Decimal(5, 2),
    
    -- Metadata
    _version UInt64,
    _snapshot_time DateTime64(3)
)
ENGINE = ReplacingMergeTree(_version)
ORDER BY (snapshot_date, vx_type, region, plant, factory, line, time_period_type)
SETTINGS allow_nullable_key = 1;

-- 重新填入資料，使用 Silver 層的補齊維度
INSERT INTO gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
SELECT
    task_create_date AS snapshot_date,
    vx_type,
    vx_type AS vx_subtype,  -- 簡化處理
    
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
    
    -- 時間維度
    'daily' AS time_period_type,
    toString(task_create_date) AS time_period_value,
    
    -- 任務統計
    COUNT(*) AS total_task_qty,
    countIf(task_status = 'TODO') AS todo_qty,
    countIf(task_status = 'DOING') AS doing_qty,
    countIf(task_status = 'DONE') AS done_qty,
    countIf(task_status IN ('DOING', 'DONE')) AS doing_done_qty,
    countIf(task_status IN ('TODO', 'DOING')) AS todo_doing_acc_qty,
    
    -- 百分比統計
    CASE WHEN COUNT(*) > 0 THEN countIf(task_status = 'TODO') * 100.0 / COUNT(*) ELSE 0 END AS todo_pct,
    CASE WHEN COUNT(*) > 0 THEN countIf(task_status = 'DOING') * 100.0 / COUNT(*) ELSE 0 END AS doing_pct,
    CASE WHEN COUNT(*) > 0 THEN countIf(task_status = 'DONE') * 100.0 / COUNT(*) ELSE 0 END AS done_pct,
    CASE WHEN COUNT(*) > 0 THEN countIf(task_status IN ('DOING', 'DONE')) * 100.0 / COUNT(*) ELSE 0 END AS doing_done_pct,
    
    -- Metadata
    1 AS _version,
    now64(3) AS _snapshot_time

FROM silver.mv_fact_task_vx_attribution_mdm
WHERE is_excluded = 0
  AND task_create_date >= '2025-01-01'  -- 限制資料範圍
GROUP BY 
    task_create_date, vx_type, region, plant, factory, line,
    region_source, plant_source, factory_source, line_source, dimension_source;

-- ========================================
-- 2. 建立 L5 儀表板摘要表
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

-- 填入資料
INSERT INTO gold.l5_dashboard_summary
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
-- 3. 更新 Cube.js 對應的 Gold 層表
-- ========================================

-- 檢查是否需要更新其他 Gold 層表
SELECT 'Gold Layer Dimension Backfill Logic Updated Successfully' AS status,
       'Rule: Trust Silver Layer Backfilled Dimensions' AS rule,
       'Updated tables: DAILY_L5_TASK_COMPLETION_SNAPSHOT, l5_dashboard_summary' AS updated_tables,
       'New fields: region, region_source, plant_source, factory_source, line_source' AS new_fields;

-- ========================================
-- 4. 驗證更新結果
-- ========================================

-- 檢查維度完整性
SELECT 
    'Dimension Completeness Check' AS check_type,
    COUNT(*) AS total_records,
    SUM(CASE WHEN region != '' THEN 1 ELSE 0 END) AS has_region,
    SUM(CASE WHEN plant != '' THEN 1 ELSE 0 END) AS has_plant,
    SUM(CASE WHEN factory != '' THEN 1 ELSE 0 END) AS has_factory,
    SUM(CASE WHEN line != '' THEN 1 ELSE 0 END) AS has_line
FROM gold.l5_dashboard_summary;

-- 檢查維度來源分布
SELECT 
    'Dimension Source Distribution' AS check_type,
    region_source,
    plant_source,
    factory_source,
    line_source,
    COUNT(*) AS record_count
FROM gold.l5_dashboard_summary
GROUP BY region_source, plant_source, factory_source, line_source
ORDER BY record_count DESC
LIMIT 10;