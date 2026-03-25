-- ========================================
-- 步驟 7: Gold Layer - KPI User Utilization (實體表模式)
-- 內容: rmv_user_utilization
-- 前置: 05_silver_dim_users, 04_silver_fact_tasks
-- ========================================

-- DROP TABLE IF EXISTS gold.rmv_user_utilization_data;

-- CREATE TABLE IF NOT EXISTS gold.rmv_user_utilization_data (
--     snapshot_date Date,
--     vx_type String,
--     region_code String,
--     plant_code String,
--     factory_code String,
--     line_name String,
--     config_users UInt64,
--     active_users UInt64,
--     utilization_rate Float64,
--     _refresh_time DateTime64(3)
-- )
-- ENGINE = ReplacingMergeTree(_refresh_time)
-- ORDER BY (snapshot_date, region_code, vx_type, plant_code, factory_code, line_name)
-- TTL snapshot_date + INTERVAL 1 YEAR;

-- -- 建立相容視圖給舊有的 API 或 Cube.js 使用
-- CREATE OR REPLACE VIEW gold.rmv_user_utilization AS
-- SELECT * FROM gold.rmv_user_utilization_data;

-- -- 驗證
-- SELECT 'gold.rmv_user_utilization' as table_name, count() as row_count FROM gold.rmv_user_utilization;
