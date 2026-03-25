-- ========================================
-- 步驟 6: Gold Layer - KPI Task Completion (Optimized for Low-RAM)
-- 內容: rmv_l5_task_completion (Summing Architecture)
-- 前置: 04_silver_fact_tasks
-- ========================================

-- 1. 建立實體儲存表 (SummingMergeTree)
-- 使用 SummingMergeTree 以支援多路徑併發寫入並自動加總
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
ENGINE = SummingMergeTree()
ORDER BY (snapshot_date, vx_type, region, plant, factory, line)
TTL snapshot_date + INTERVAL 1 YEAR;

-- 2. 建立最終對接視圖 (The "Original Name" View for Cube.js/Superset)
-- 此視圖確保查詢時資料已完全聚合。
CREATE VIEW IF NOT EXISTS gold.rmv_l5_task_completion AS
SELECT
    snapshot_date,
    vx_type,
    region, plant, factory, line,
    sum(total_task) AS total_task,
    sum(todo_count) AS todo_count,
    sum(doing_count) AS doing_count,
    sum(done_count) AS done_count,
    sum(acc_todo_doing) AS acc_todo_doing,
    max(_refresh_time) AS _refresh_time
FROM gold.rmv_l5_task_completion_phys
GROUP BY snapshot_date, vx_type, region, plant, factory, line;

-- Schema End (INSERT logic is handled by execute_etl.py)
