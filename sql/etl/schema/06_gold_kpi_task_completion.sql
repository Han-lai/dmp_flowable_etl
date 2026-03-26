-- ========================================
-- 步驟 6: Gold Layer - KPI Task Completion
-- 內容: rmv_l5_task_completion (ReplacingMergeTree Architecture)
-- 前置: 04_silver_fact_tasks
-- ========================================

-- 1. 建立實體儲存表 (ReplacingMergeTree)
-- 使用 ReplacingMergeTree 確保跨窗口 ETL 的幂等性（同維度組合保留最新版本）
CREATE TABLE IF NOT EXISTS gold.rmv_l5_task_completion_phys (
    snapshot_date Date,
    vx_type String,
    region String,
    plant String,
    factory String,
    line String,
    total_task Int64,
    todo_count Int64,
    doing_count Int64,
    done_count Int64,
    acc_todo_doing Int64,
    _refresh_time DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (snapshot_date, vx_type, region, plant, factory, line)
TTL snapshot_date + INTERVAL 1 YEAR;

-- 2. 建立最終對接視圖 (The "Original Name" View for Cube.js/Superset)
-- 使用 FINAL 確保讀取時已去重
CREATE VIEW IF NOT EXISTS gold.rmv_l5_task_completion AS
SELECT
    snapshot_date,
    vx_type,
    region, plant, factory, line,
    total_task,
    todo_count,
    doing_count,
    done_count,
    acc_todo_doing,
    _refresh_time
FROM gold.rmv_l5_task_completion_phys FINAL;

-- Schema End (INSERT logic is handled by execute_etl.py)
