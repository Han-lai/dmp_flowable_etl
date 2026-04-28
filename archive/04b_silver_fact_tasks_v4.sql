-- ========================================
-- 步驟 4b: Silver Layer - Fact Tasks V4 (獨立版本)
-- 內容: mv_fact_task_vx_v4 (V4 bypass 邏輯版本)
-- 說明: 此表與 mv_fact_task_vx 結構相同，但套用 V4 bypass 規則：
--       assignee_name = 'SYSTEM' 的任務一律標記為 system_bypass
-- 前置: 03_silver_pivot_and_hierarchy (共用)
-- ========================================

-- DROP TABLE IF EXISTS silver.mv_fact_task_vx_v4;

CREATE TABLE IF NOT EXISTS silver.mv_fact_task_vx_v4 (
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
PARTITION BY toYYYYMM(task_primary_date)
ORDER BY (task_id)
TTL task_primary_date + INTERVAL 1 YEAR
SETTINGS allow_nullable_key = 1;
