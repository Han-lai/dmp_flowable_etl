-- ========================================
-- 步驟 6: Gold Layer - KPI Task Completion
-- 內容: rmv_l5_task_completion
-- 前置: 04_silver_fact_tasks
-- ========================================

-- 啟用 REFRESHABLE MView 實驗功能 (ClickHouse 24.3 需要)
SET allow_experimental_refreshable_materialized_view = 1;

-- DROP TABLE IF EXISTS gold.rmv_l5_task_completion;

-- 建立實體表來儲存資料，避免實驗性的 Refreshable MView 在重啟時遺失內部表 (.inner_id_*)
CREATE TABLE IF NOT EXISTS gold.rmv_l5_task_completion_data (
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
    completion_rate Float64,
    execution_rate Float64,
    acc_todo_doing UInt64,
    _refresh_time DateTime64(3)
)
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (snapshot_date, vx_type, region, plant, factory, line)
TTL snapshot_date + INTERVAL 1 YEAR;

CREATE MATERIALIZED VIEW IF NOT EXISTS gold.rmv_l5_task_completion
REFRESH EVERY 1 DAY OFFSET 4 HOUR
TO gold.rmv_l5_task_completion_data
AS
WITH 
-- 1. 基礎 Daily 事件統計 (與原本邏輯一致)
daily_base AS (
    SELECT
        snapshot_date,
        vx_type,
        region, plant, factory, line,
        count() AS total_task,
        countIf(snapshot_date < toDate(task_claim_date) OR (snapshot_date < toDate(task_end_date) AND task_claim_date IS NULL)) AS todo_count,
        countIf(snapshot_date >= toDate(task_claim_date) AND (snapshot_date < toDate(task_end_date) OR task_end_date IS NULL)) AS doing_count,
        countIf(snapshot_date >= toDate(task_end_date) AND task_end_date IS NULL = 0) AS done_count
    FROM silver.mv_fact_task_vx FINAL
    ARRAY JOIN arrayDistinct(arrayFilter(d -> d IS NOT NULL, [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
    WHERE is_excluded = 0
    GROUP BY snapshot_date, vx_type, region, plant, factory, line
),
-- 2. Rolling Acc 統計 (計算 D-6 ~ D 的在途任務去重)
-- 優化：由 CROSS JOIN 改為 ARRAY JOIN，將 7.5 億次運算降為 1000 萬次，防止 OOM
acc_stats AS (
    SELECT
        snapshot_date,
        vx_type,
        region, plant, factory, line,
        uniqExact(task_id) AS acc_todo_doing
    FROM (
        SELECT
            task_id,
            vx_type,
            region, plant, factory, line,
            -- 計算 7 天滑動視窗日期陣列
            -- 邏輯：從 task_start_date 開始，直到 (task_end_date 或 建立+7天 或 認領+7天) 之中最早的一個
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
    GROUP BY snapshot_date, vx_type, region, plant, factory, line
)
SELECT
    COALESCE(base.snapshot_date, acc.snapshot_date) AS snapshot_date,
    COALESCE(base.vx_type, acc.vx_type) AS vx_type,
    COALESCE(base.region, acc.region) AS region,
    COALESCE(base.plant, acc.plant) AS plant,
    COALESCE(base.factory, acc.factory) AS factory,
    COALESCE(base.line, acc.line) AS line,
    
    -- 基礎指標
    COALESCE(base.total_task, 0) AS total_task,
    COALESCE(base.todo_count, 0) AS todo_count,
    COALESCE(base.doing_count, 0) AS doing_count,
    COALESCE(base.done_count, 0) AS done_count,
    
    -- 完成率與執行率
    round(COALESCE(base.done_count, 0) * 100.0 / NULLIF(COALESCE(base.total_task, 0), 0), 2) AS completion_rate,
    round((COALESCE(base.doing_count, 0) + COALESCE(base.done_count, 0)) * 100.0 / NULLIF(COALESCE(base.total_task, 0), 0), 2) AS execution_rate,
    
    -- 累積指標 (Acc)
    COALESCE(acc.acc_todo_doing, 0) AS acc_todo_doing,

    now64(3) AS _refresh_time
FROM daily_base AS base
FULL OUTER JOIN acc_stats AS acc USING (snapshot_date, vx_type, region, plant, factory, line);

-- 手動觸發首次刷新
SYSTEM REFRESH VIEW gold.rmv_l5_task_completion;

-- 驗證
SELECT 'rmv_l5_task_completion' AS table_name, count() AS row_count 
FROM gold.rmv_l5_task_completion;

SELECT 'Step 5: Gold L5 Task Completion Done' AS status;
