-- ========================================
-- 步驟 6: Gold Layer - KPI Task Completion
-- 內容: 2-Tier Gold Architecture
--   6a. rmv_l5_milestone_phys  - Todo/Doing/Done 里程碑計數 (中間表)
--   6b. rmv_l5_acc_phys        - 7 天滾動 ACC 計數 (中間表)
--   6c. rmv_l5_task_completion_phys - Milestone + ACC 合併後的最終主表
--   6d. rmv_l5_task_completion - BI 對接 View (供 Cube.js / Superset)
-- 前置: 04_silver_fact_tasks
-- ========================================

-- ----------------------------------------
-- 6a. 中間表: Milestone (Todo/Doing/Done)
--     由 backfill_gold_milestone.sql 寫入
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS gold.rmv_l5_milestone_phys (
    snapshot_date Date,
    vx_type       String,
    region        String,
    plant         String,
    factory       String,
    line          String,
    total_task    Int64,
    todo_count    Int64,
    doing_count   Int64,
    done_count    Int64,
    _refresh_time DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (snapshot_date, vx_type, region, plant, factory, line)
TTL snapshot_date + INTERVAL 1 YEAR;

-- ----------------------------------------
-- 6b. 中間表: ACC (7-Day Rolling Accumulation)
--     由 backfill_gold_acc.sql 寫入
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS gold.rmv_l5_acc_phys (
    snapshot_date  Date,
    vx_type        String,
    region         String,
    plant          String,
    factory        String,
    line           String,
    acc_todo_doing Int64,
    _refresh_time  DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (snapshot_date, vx_type, region, plant, factory, line)
TTL snapshot_date + INTERVAL 1 YEAR;

-- ----------------------------------------
-- 6c. 最終主表: Milestone + ACC 合併
--     使用 ReplacingMergeTree 確保跨窗口 ETL 的幂等性
--     由 backfill_gold.sql (FULL OUTER JOIN) 寫入
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS gold.rmv_l5_task_completion_phys (
    snapshot_date  Date,
    vx_type        String,
    region         String,
    plant          String,
    factory        String,
    line           String,
    total_task     Int64,
    todo_count     Int64,
    doing_count    Int64,
    done_count     Int64,
    acc_todo_doing Int64,
    _refresh_time  DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (snapshot_date, vx_type, region, plant, factory, line)
TTL snapshot_date + INTERVAL 1 YEAR;

-- ----------------------------------------
-- 6d. BI 對接 View (Cube.js / Superset)
--     使用 FINAL 確保讀取時已去重
-- ----------------------------------------
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

-- Schema End (INSERT logic is handled by execute_etl.py / backfill_gold*.sql)
