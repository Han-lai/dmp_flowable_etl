-- ========================================
-- 步驟 6: Gold Layer - KPI Task Completion (V3 Bitmap Architecture)
-- 內容: 2-Tier Gold Architecture
--   6a. rmv_l5_milestone_phys       - Todo/Doing/Done Bitmap 里程碑 (中間表)
--   6b. rmv_l5_acc_phys             - 7 天滾動 ACC Bitmap (中間表)
--   6c. rmv_l5_task_completion_phys - Milestone + ACC 合併後的最終主表
--   6d. rmv_l5_task_completion      - BI 對接 View (供 Cube.js / Superset)
-- 前置: 04_silver_fact_tasks
-- 引擎: AggregatingMergeTree (支援 bitmap OR 合併，對應 groupBitmapState/groupBitmapMergeState)
-- ========================================

-- ----------------------------------------
-- 6a. 中間表: Milestone (Todo/Doing/Done Bitmap)
--     由 backfill_gold_milestone.sql 寫入
--     欄位類型: AggregateFunction(groupBitmap, UInt64)
--     對應插入: groupBitmapStateIf(cityHash64(task_id), ...)
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS gold.rmv_l5_milestone_phys (
    snapshot_date Date,
    vx_type       String,
    region        String,
    plant         String,
    factory       String,
    line          String,
    todo_daily       AggregateFunction(groupBitmap, UInt64),
    doing_daily      AggregateFunction(groupBitmap, UInt64),
    done_daily       AggregateFunction(groupBitmap, UInt64),
    todo_weekly      AggregateFunction(groupBitmap, UInt64),
    doing_weekly     AggregateFunction(groupBitmap, UInt64),
    done_weekly      AggregateFunction(groupBitmap, UInt64),
    todo_monthly     AggregateFunction(groupBitmap, UInt64),
    doing_monthly    AggregateFunction(groupBitmap, UInt64),
    done_monthly     AggregateFunction(groupBitmap, UInt64),
    -- [New] 週期標籤
    calendar_year UInt16,
    iso_year      UInt16,
    iso_week      UInt8,
    iso_month     UInt8,
    _refresh_time SimpleAggregateFunction(max, DateTime64(3))
)
ENGINE = AggregatingMergeTree()
ORDER BY (snapshot_date, calendar_year, iso_year, iso_week, vx_type, region, plant, factory, line)
TTL snapshot_date + INTERVAL 1 YEAR;

-- ----------------------------------------
-- 6b. 中間表: ACC (7-Day Rolling Accumulation Bitmap)
--     由 backfill_gold_acc.sql 寫入
--     欄位類型: AggregateFunction(groupBitmap, UInt64)
--     對應插入: groupBitmapState(cityHash64(task_id))
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS gold.rmv_l5_acc_phys (
    snapshot_date  Date,
    vx_type        String,
    region         String,
    plant          String,
    factory        String,
    line           String,
    acc         AggregateFunction(groupBitmap, UInt64),
    acc_total_task AggregateFunction(groupBitmap, UInt64), -- 新增

    -- [New] 週期標籤
    calendar_year UInt16,
    iso_year      UInt16,
    iso_week      UInt8,
    iso_month     UInt8,
    _refresh_time  SimpleAggregateFunction(max, DateTime64(3))
)
ENGINE = AggregatingMergeTree()
ORDER BY (snapshot_date, calendar_year, iso_year, iso_week, vx_type, region, plant, factory, line)
TTL snapshot_date + INTERVAL 1 YEAR;

-- ----------------------------------------
-- 6c. 最終主表: Milestone + ACC 合併 (Unified Bitmap)
--     使用 AggregatingMergeTree 確保跨窗口 ETL 的 bitmap OR 冪等合併
--     由 backfill_gold.sql (LEFT JOIN milestone + acc) 寫入
--     欄位對應:
--       total_task = bitmapOr(todo, doing, done)
--       todo / doing / done = 來自 rmv_l5_milestone_phys
--       acc = 來自 rmv_l5_acc_phys
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS gold.rmv_l5_task_completion_phys (
    snapshot_date  Date,
    vx_type        String,
    region         String,
    plant          String,
    factory        String,
    line           String,
    total_task  AggregateFunction(groupBitmap, UInt64), -- 總任務量 Bitmap (去重聯集)
    todo_daily  AggregateFunction(groupBitmap, UInt64),  -- 當日待辦任務集合
    doing_daily AggregateFunction(groupBitmap, UInt64), -- 當日執行中任務集合
    done_daily  AggregateFunction(groupBitmap, UInt64), -- 當日完成任務集合
    todo_weekly  AggregateFunction(groupBitmap, UInt64), -- 當週待辦任務集合
    doing_weekly AggregateFunction(groupBitmap, UInt64), -- 當週執行中任務集合
    done_weekly  AggregateFunction(groupBitmap, UInt64), -- 當週完成任務集合
    todo_monthly  AggregateFunction(groupBitmap, UInt64), -- 當月待辦任務集合
    doing_monthly AggregateFunction(groupBitmap, UInt64), -- 當月執行中任務集合
    done_monthly  AggregateFunction(groupBitmap, UInt64), -- 當月完成任務集合
    acc         AggregateFunction(groupBitmap, UInt64), -- 7 天滾動累計任務集合
    acc_total_task AggregateFunction(groupBitmap, UInt64), -- 新增

    -- [New] 週期標籤
    calendar_year UInt16,
    iso_year      UInt16,
    iso_week      UInt8,
    iso_month     UInt8,
    _refresh_time  SimpleAggregateFunction(max, DateTime64(3))
)
ENGINE = AggregatingMergeTree()
ORDER BY (snapshot_date, calendar_year, iso_year, iso_week, vx_type, region, plant, factory, line)
TTL snapshot_date + INTERVAL 1 YEAR;

-- ----------------------------------------
-- 6d. BI 對接 View (Cube.js / Superset)
--     注意: AggregatingMergeTree 讀取時透過 groupBitmapMergeState 在 Query 層完成合併
--     Cube.js model 使用 groupBitmapMergeState + bitmapCardinality 計算精確去重數值
-- ----------------------------------------
CREATE VIEW IF NOT EXISTS gold.rmv_l5_task_completion AS
SELECT
    snapshot_date,
    vx_type,
    region, plant, factory, line,
    total_task,
    todo_daily,
    doing_daily,
    done_daily,
    todo_weekly,
    doing_weekly,
    done_weekly,
    todo_monthly,
    doing_monthly,
    done_monthly,
    acc,
    acc_total_task, -- 新增

    calendar_year,
    iso_year,
    iso_week,
    iso_month,
    _refresh_time
FROM gold.rmv_l5_task_completion_phys;

-- Schema End (INSERT logic is handled by execute_etl.py / backfill_gold*.sql)

