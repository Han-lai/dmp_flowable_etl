-- ========================================
-- 步驟 7: Gold Layer - KPI User Utilization
-- 內容: rmv_user_utilization
-- 前置: 05_silver_dim_users, 04_silver_fact_tasks
-- ========================================

SET allow_experimental_refreshable_materialized_view = 1;

-- DROP TABLE IF EXISTS gold.rmv_user_utilization;

-- 建立實體表來儲存資料，避免實驗性的 Refreshable MView 在重啟時遺失內部表 (.inner_id_*)
CREATE TABLE IF NOT EXISTS gold.rmv_user_utilization_data (
    snapshot_date Date,
    vx_type String,
    region_code String,
    plant_code String,
    factory_code String,
    line_name String,
    config_users UInt64,
    active_users UInt64,
    utilization_rate Float64,
    _refresh_time DateTime64(3)
)
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (snapshot_date, region_code, vx_type, plant_code, factory_code, line_name)
TTL snapshot_date + INTERVAL 1 YEAR;

CREATE MATERIALIZED VIEW IF NOT EXISTS gold.rmv_user_utilization
REFRESH EVERY 1 DAY OFFSET 5 HOUR
TO gold.rmv_user_utilization_data
AS
WITH 
-- 1. 時間範圍 (過去 365 天)
DateRange AS (
    SELECT toDate(today() - number) as snapshot_date
    FROM system.numbers
    LIMIT 365
),

-- 2. 活躍人員 (Active Users)
ActiveData AS (
    SELECT 
        snapshot_date,
        assignee_code as emp_code
    FROM silver.mv_fact_task_vx
    ARRAY JOIN arrayDistinct(arrayFilter(d -> d IS NOT NULL, [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
    WHERE is_excluded = 0 
      AND task_status IN ('DOING', 'DONE')
      AND assignee_code != ''
      AND snapshot_date >= today() - 365
)

SELECT
    -- 時間
    d.snapshot_date,
    
    -- 維度 (來自 Config Users 配置)
    u.final_vx_type as vx_type,
    u.region_code as region_code,
    u.plant_code as plant_code,
    COALESCE(u.factory_code, '') as factory_code,
    COALESCE(u.line_name, '') as line_name,
    
    -- 指標
    count(DISTINCT u.emp_code) as config_users,
    count(DISTINCT CASE WHEN a.emp_code IS NOT NULL THEN u.emp_code ELSE NULL END) as active_users,
    
    -- 使用率 (Active / Config)
    round(count(DISTINCT CASE WHEN a.emp_code IS NOT NULL THEN u.emp_code ELSE NULL END) * 100.0 
          / nullIf(count(DISTINCT u.emp_code), 0), 2) as utilization_rate,
          
    now64(3) as _refresh_time

FROM silver.dim_config_users u
CROSS JOIN DateRange d -- 每一天
LEFT JOIN ActiveData a ON u.emp_code = a.emp_code AND d.snapshot_date = a.snapshot_date

GROUP BY d.snapshot_date, u.final_vx_type, u.region_code, u.plant_code, u.factory_code, u.line_name;

-- 驗證
SELECT 'gold.rmv_user_utilization' as table_name, count() as row_count FROM gold.rmv_user_utilization;
