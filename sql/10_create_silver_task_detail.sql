-- ============================================
-- Silver 層 - 任務明細寬表
-- 等價於 MSSQL Reference SQL
-- 建立日期：2026-01-16
-- ============================================

-- ============================================
-- 表 1: varinst_process_pivot
-- 用途：流程層級變數寬表
-- ============================================

DROP TABLE IF EXISTS silver.varinst_process_pivot;

CREATE TABLE silver.varinst_process_pivot
(
    proc_inst_id String,
    plant Nullable(String),
    factory Nullable(String),
    production_area Nullable(String),
    line_name Nullable(String),
    model_name Nullable(String),
    delivery_area Nullable(String),
    schedule_number Nullable(String),
    mo_number Nullable(String),
    sap_plant Nullable(String),
    sap_product_group Nullable(String),
    pallet Nullable(String),
    transfer_no Nullable(String),
    q_block_event_id Nullable(String),
    defect_sn Nullable(String),
    time_key Nullable(String),
    region Nullable(String),
    _transform_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_transform_time)
ORDER BY (proc_inst_id)
SETTINGS index_granularity = 8192;

-- ============================================
-- 表 2: varinst_task_pivot
-- 用途：Task 層級變數寬表
-- ============================================

DROP TABLE IF EXISTS silver.varinst_task_pivot;

CREATE TABLE silver.varinst_task_pivot
(
    task_id String,
    auto_complete Nullable(Int64),
    _transform_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_transform_time)
ORDER BY (task_id)
SETTINGS index_granularity = 8192;

-- ============================================
-- 表 3: task_detail_wide
-- 用途：任務明細寬表（核心 Silver 表）
-- ============================================

DROP TABLE IF EXISTS silver.task_detail_wide;

CREATE TABLE silver.task_detail_wide
(
    -- 主鍵
    task_id String,
    
    -- 流程資訊
    proc_inst_id String,
    proc_def_id Nullable(String),
    process_definition_key Nullable(String),
    process_definition_name Nullable(String),
    business_key Nullable(String),
    delete_reason Nullable(String),
    
    -- 任務資訊
    task_definition_key Nullable(String),
    task_name Nullable(String),
    task_status LowCardinality(String),
    task_bypass LowCardinality(String),
    task_assignee Nullable(String),
    task_assignee_account Nullable(String),
    task_assignee_name Nullable(String),
    
    -- 時間欄位
    task_create_time DateTime64(3),
    task_claim_time Nullable(DateTime64(3)),
    task_end_time Nullable(DateTime64(3)),
    task_create_date Date,
    
    -- 計算欄位
    task_duration_minutes Nullable(Float64),
    task_work_minutes Nullable(Float64),
    
    -- 流程變數（維度）
    plant Nullable(String),
    factory Nullable(String),
    production_area Nullable(String),
    line Nullable(String),
    model_name Nullable(String),
    delivery_area Nullable(String),
    schedule_number Nullable(String),
    mo_number Nullable(String),
    sap_plant Nullable(String),
    sap_product_group Nullable(String),
    pallet Nullable(String),
    transfer_no Nullable(String),
    q_block_event_id Nullable(String),
    defect_sn Nullable(String),
    time_key Nullable(String),
    region Nullable(String),
    
    -- Metadata
    _transform_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_transform_time)
PARTITION BY toYYYYMM(task_create_date)
ORDER BY (task_create_date, task_id)
SETTINGS index_granularity = 8192;
