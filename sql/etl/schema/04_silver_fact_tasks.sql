-- ========================================
-- 步驟 4: Silver Layer - Fact Tasks (Vx)
-- 內容: mv_fact_task_vx (Core Fact Table)
-- 前置: 03_silver_pivot_and_hierarchy
-- ========================================

-- DROP TABLE IF EXISTS silver.mv_fact_task_vx;

CREATE TABLE IF NOT EXISTS silver.mv_fact_task_vx (
    task_id String,
    task_start_time DateTime64(3),
    task_claim_time Nullable(DateTime64(3)),
    task_end_time Nullable(DateTime64(3)),
    task_start_date Date,
    task_claim_date Nullable(Date),
    task_end_date Nullable(Date),
    task_primary_date Date,


    task_create_date Date,
    task_status String,
    vx_type String,
    region String,
    plant String,
    factory String,
    line String,
    region_source String,
    plant_source String,
    factory_source String,
    line_source String,
    is_excluded UInt8,
    exclude_reason String,
    assignee_code String,
    assignee_name String,
    task_definition_key String,
    task_name String,
    mo_number String,
    proc_inst_id String,
    _mview_update_time DateTime64(3)
)
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (task_id)
TTL task_primary_date + INTERVAL 1 YEAR
SETTINGS allow_nullable_key = 1;

-- -- 驗證資料量
-- SELECT 'mv_fact_task_vx' AS table_name, count() AS row_count 
-- FROM silver.mv_fact_task_vx;

-- -- 驗證新增的時間維度欄位
-- SELECT 
--     'time_dimensions' AS check_name,
--     count() AS total,
--     countIf(task_start_date IS NOT NULL) AS with_start_date,
--     countIf(task_claim_date IS NOT NULL) AS with_claim_date,
--     countIf(task_end_date IS NOT NULL) AS with_end_date
-- FROM silver.mv_fact_task_vx FINAL;

-- -- 驗證 Vx 分布
-- SELECT vx_type, count() AS cnt 
-- FROM silver.mv_fact_task_vx FINAL
-- GROUP BY vx_type 
-- ORDER BY cnt DESC;

-- SELECT 'Silver Layer 2 (v2 多時間維度) 完成' AS status;
