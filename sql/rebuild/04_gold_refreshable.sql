-- ========================================
-- 步驟 5-6: Gold 層 REFRESHABLE MView
-- 執行時間: 約 2 分鐘
-- 前置條件: 03_silver_layer2.sql 執行完成
-- 特性: 每小時自動刷新
-- ========================================

-- ========================================
-- 5. L5 任務完成率 (每小時自動刷新)
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

-- ========================================
-- 6. 人員使用率 (每小時自動刷新)
-- ========================================
DROP TABLE IF EXISTS gold.rmv_user_utilization;

CREATE MATERIALIZED VIEW gold.rmv_user_utilization
REFRESH EVERY 1 HOUR
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (snapshot_date, vx_type, plant)
TTL snapshot_date + INTERVAL 1 YEAR
AS
SELECT
    snapshot_date,
    vx_type,
    plant,
    
    -- 人員統計
    count(DISTINCT assignee_code) AS active_users,
    countIf(DISTINCT assignee_code, task_status IN ('TODO', 'DOING')) AS working_users,
    countIf(DISTINCT assignee_code, task_status = 'DONE') AS completed_users,
    
    -- 使用率
    round(countIf(DISTINCT assignee_code, task_status IN ('TODO', 'DOING')) * 100.0 
          / nullIf(count(DISTINCT assignee_code), 0), 2) AS utilization_rate,
    
    -- 任務統計
    count() AS total_tasks,
    countIf(task_status = 'DONE') AS done_tasks,
    
    now64(3) AS _refresh_time
    
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayDistinct(arrayFilter(d -> d IS NOT NULL, [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
WHERE is_excluded = 0
  AND assignee_code IS NOT NULL AND assignee_code != ''
  AND snapshot_date >= today() - INTERVAL 1 YEAR
GROUP BY snapshot_date, vx_type, plant;

-- 手動觸發首次刷新
SYSTEM REFRESH VIEW gold.rmv_user_utilization;

-- 驗證
SELECT 'rmv_user_utilization' AS table_name, count() AS row_count 
FROM gold.rmv_user_utilization;

-- 檢查 REFRESHABLE MView 狀態
SELECT 
    database, name, 
    engine
FROM system.tables 
WHERE database = 'gold' AND name LIKE 'rmv_%';

SELECT 'Gold 層 REFRESHABLE MView 建立完成' AS status;
