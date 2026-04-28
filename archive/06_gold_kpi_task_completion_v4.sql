-- ========================================
-- 步驟 6 (V4): Gold Layer - KPI Task Completion (Activity Mode)
-- 內容: V4 專用表架構 (帶有 _v4 字尾)
--   6a. rmv_l5_milestone_v4_phys       - 日動作里程碑 (Todo/Doing/Done)
--   6b. rmv_l5_acc_v4_phys             - 7 天活動 WIP (Todo + Doing)
--   6c. rmv_l5_task_completion_v4_phys - 最終合併表
--   6d. rmv_l5_task_completion_v4      - BI 對接 View
-- ========================================

-- 6a. 動作里程碑
CREATE TABLE IF NOT EXISTS gold.rmv_l5_milestone_v4_phys (
    snapshot_date Date,
    vx_type       String,
    region        String,
    plant         String,
    factory       String,
    line          String,
    todo       AggregateFunction(groupBitmap, UInt64),
    doing      AggregateFunction(groupBitmap, UInt64),
    done       AggregateFunction(groupBitmap, UInt64),
    _refresh_time SimpleAggregateFunction(max, DateTime64(3))
)
ENGINE = AggregatingMergeTree()
ORDER BY (snapshot_date, vx_type, region, plant, factory, line);

-- 6b. 7天活動 WIP (Acc)
CREATE TABLE IF NOT EXISTS gold.rmv_l5_acc_v4_phys (
    snapshot_date  Date,
    vx_type        String,
    region         String,
    plant          String,
    factory        String,
    line           String,
    acc         AggregateFunction(groupBitmap, UInt64),
    _refresh_time  SimpleAggregateFunction(max, DateTime64(3))
)
ENGINE = AggregatingMergeTree()
ORDER BY (snapshot_date, vx_type, region, plant, factory, line);

-- 6c. 最終合併表
CREATE TABLE IF NOT EXISTS gold.rmv_l5_task_completion_v4_phys (
    snapshot_date  Date,
    vx_type        String,
    region         String,
    plant          String,
    factory        String,
    line           String,
    total_task  AggregateFunction(groupBitmap, UInt64), -- BitmapOr(todo, doing, done)
    todo        AggregateFunction(groupBitmap, UInt64),
    doing       AggregateFunction(groupBitmap, UInt64),
    done        AggregateFunction(groupBitmap, UInt64),
    acc         AggregateFunction(groupBitmap, UInt64),
    _refresh_time  SimpleAggregateFunction(max, DateTime64(3))
)
ENGINE = AggregatingMergeTree()
ORDER BY (snapshot_date, vx_type, region, plant, factory, line);

-- 6d. BI 對接 View
CREATE VIEW IF NOT EXISTS gold.rmv_l5_task_completion_v4 AS
SELECT
    snapshot_date,
    vx_type, region, plant, factory, line,
    total_task, todo, doing, done, acc,
    _refresh_time
FROM gold.rmv_l5_task_completion_v4_phys;
