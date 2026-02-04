-- ========================================
-- 步驟 6: Gold Layer - KPI Task Completion
-- 內容: rmv_l5_task_completion
-- 前置: 04_silver_fact_tasks
-- ========================================

-- 啟用 REFRESHABLE MView 實驗功能 (ClickHouse 24.3 需要)
SET allow_experimental_refreshable_materialized_view = 1;

DROP TABLE IF EXISTS gold.rmv_l5_task_completion;

CREATE MATERIALIZED VIEW gold.rmv_l5_task_completion
REFRESH EVERY 1 HOUR
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (snapshot_date, vx_type, region, plant, factory, line)
TTL snapshot_date + INTERVAL 1 YEAR
AS
WITH daily_stats AS (
    SELECT
        snapshot_date,
        vx_type,
        region, plant, factory, line,
        task_id,
        task_claim_date,
        task_end_date
    FROM silver.mv_fact_task_vx FINAL
    ARRAY JOIN arrayDistinct(arrayFilter(d -> d IS NOT NULL, [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
    WHERE is_excluded = 0
)
SELECT
    snapshot_date,
    vx_type,
    region, plant, factory, line,
    
    -- 基礎統計
    count() AS total_task,
    countIf(snapshot_date < toDate(task_claim_date) OR (snapshot_date < toDate(task_end_date) AND task_claim_date IS NULL)) AS todo_count,
    countIf(snapshot_date >= toDate(task_claim_date) AND (snapshot_date < toDate(task_end_date) OR task_end_date IS NULL)) AS doing_count,
    countIf(snapshot_date >= toDate(task_end_date) AND task_end_date IS NULL = 0) AS done_count,
    
    -- 完成率與執行率
    round(countIf(snapshot_date >= toDate(task_end_date) AND task_end_date IS NULL = 0) * 100.0 / count(), 2) AS completion_rate,
    round(countIf(snapshot_date >= toDate(task_claim_date)) * 100.0 / count(), 2) AS execution_rate,
    
    -- 滑動視窗 Acc (Todo + Doing)
    -- 此處邏輯：當日有活動的任務中，計算截至當日尚未結束的數值。
    -- 注意：根據業務定義，Acc 是計算 [D-6, D] 區間。
    -- 在 MView 中為了效能，我們改用 Join 或在查詢層計算。
    -- 這裡先實作跟 Daily 一致的基底，供後續 View 使用。
    (countIf(snapshot_date < toDate(task_claim_date) OR (snapshot_date < toDate(task_end_date) AND task_claim_date IS NULL)) + 
     countIf(snapshot_date >= toDate(task_claim_date) AND (snapshot_date < toDate(task_end_date) OR task_end_date IS NULL))) AS acc_todo_doing,

    now64(3) AS _refresh_time
FROM daily_stats
GROUP BY snapshot_date, vx_type, region, plant, factory, line;

-- 手動觸發首次刷新
SYSTEM REFRESH VIEW gold.rmv_l5_task_completion;

-- 驗證
SELECT 'rmv_l5_task_completion' AS table_name, count() AS row_count 
FROM gold.rmv_l5_task_completion;

SELECT 'Step 5: Gold L5 Task Completion Done' AS status;
