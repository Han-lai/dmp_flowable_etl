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
SELECT
    snapshot_date,
    vx_type,
    region, plant, factory, line,
    
    -- 任務統計
    count() AS total_task,
    countIf(task_status = 'TODO') AS todo_count,
    countIf(task_status = 'DOING') AS doing_count,
    countIf(task_status = 'DONE') AS done_count,
    
    -- 完成率
    round(countIf(task_status = 'DONE') * 100.0 / count(), 2) AS completion_rate,
    
    -- 執行率 (DOING + DONE)
    round((countIf(task_status = 'DOING') + countIf(task_status = 'DONE')) * 100.0 / count(), 2) AS execution_rate,
    
    now64(3) AS _refresh_time
    
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayDistinct(arrayFilter(d -> d IS NOT NULL, [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
WHERE is_excluded = 0
  AND snapshot_date >= today() - INTERVAL 1 YEAR
GROUP BY snapshot_date, vx_type, region, plant, factory, line;

-- 手動觸發首次刷新
SYSTEM REFRESH VIEW gold.rmv_l5_task_completion;

-- 驗證
SELECT 'rmv_l5_task_completion' AS table_name, count() AS row_count 
FROM gold.rmv_l5_task_completion;

SELECT 'Step 5: Gold L5 Task Completion Done' AS status;
