-- ========================================
-- 步驟 6: Gold Layer - KPI Task Completion (Optimized for Low-RAM)
-- 內容: rmv_l5_task_completion (Summing Architecture)
-- 前置: 04_silver_fact_tasks
-- ========================================

-- 1. 建立實體儲存表 (SummingMergeTree)
-- 使用 SummingMergeTree 以支援多路徑併發寫入並自動加總
-- DROP TABLE IF EXISTS gold.rmv_l5_task_completion_data_phys;

CREATE TABLE gold.rmv_l5_task_completion_data_phys (
    snapshot_date Date,
    vx_type String,
    region String,
    plant String,
    factory String,
    line String,
    total_task UInt64,
    todo_count UInt64,
    doing_count UInt64,
    done_count UInt64,
    acc_todo_doing UInt64,
    _refresh_time DateTime64(3) DEFAULT now()
)
ENGINE = SummingMergeTree()
ORDER BY (snapshot_date, vx_type, region, plant, factory, line)
TTL snapshot_date + INTERVAL 1 YEAR;

-- 2. 建立外部對接視圖 (Seamless View for Superset/API/Cube)
-- 移除 Rate 計算，由前端或 Cube.js 處理。僅提供原始加總。
-- DROP VIEW IF EXISTS gold.rmv_l5_task_completion_data;

CREATE VIEW gold.rmv_l5_task_completion_data AS
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
FROM gold.rmv_l5_task_completion_data_phys
GROUP BY snapshot_date, vx_type, region, plant, factory, line;

-- 3. 建立相容視圖
-- DROP VIEW IF EXISTS gold.rmv_l5_task_completion;
CREATE VIEW gold.rmv_l5_task_completion AS SELECT * FROM gold.rmv_l5_task_completion_data;

-- [核心邏輯 A] 基礎 Daily 統計 (恢復 V2 原始算法)
INSERT INTO gold.rmv_l5_task_completion_data_phys 
SELECT
    snapshot_date, vx_type, region, plant, factory, line,
    count() AS total_task,
    countIf(snapshot_date < toDate(task_claim_date) OR (snapshot_date < toDate(task_end_date) AND task_claim_date IS NULL)) AS todo_count,
    countIf(snapshot_date >= toDate(task_claim_date) AND (snapshot_date < toDate(task_end_date) OR task_end_date IS NULL)) AS doing_count,
    countIf(snapshot_date >= toDate(task_end_date) AND task_end_date IS NULL = 0) AS done_count,
    toUInt64(0) AS acc_todo_doing,
    now() as _refresh_time
FROM silver.mv_fact_task_vx
ARRAY JOIN arrayDistinct(arrayFilter(d -> d IS NOT NULL, [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
WHERE is_excluded = 0
GROUP BY snapshot_date, vx_type, region, plant, factory, line;

-- [核心邏輯 B] 累積在途統計 (恢復 V2 原始精度 - 移除 7 天限制)
-- 透過獨立 INSERT 執行以降低記憶體壓力
INSERT INTO gold.rmv_l5_task_completion_data_phys
SELECT
    snapshot_date, vx_type, region, plant, factory, line,
    toUInt64(0) AS total_task,
    toUInt64(0) AS todo_count,
    toUInt64(0) AS doing_count,
    toUInt64(0) AS done_count,
    uniqExact(task_id) AS acc_todo_doing,
    now() as _refresh_time
FROM (
    SELECT
        task_id, vx_type, region, plant, factory, line,
        -- 恢復 V2 原始原始 7 天滑動視窗邏輯
        arrayMap(d -> toDate(d), 
            range(
                toUInt32(task_start_date), 
                toUInt32(least(
                    COALESCE(task_end_date, today() + 2), 
                    greatest(task_start_date, COALESCE(task_claim_date, task_start_date)) + 7
                ))
            )
        ) AS dates
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0
)
ARRAY JOIN dates AS snapshot_date
GROUP BY snapshot_date, vx_type, region, plant, factory, line;
