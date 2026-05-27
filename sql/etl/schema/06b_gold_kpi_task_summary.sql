-- ========================================
-- 步驟 6e: Gold Layer - Pre-computed Task Summary
-- 內容: 預聚合整數表 (取代 Cube 即時 bitmap merge)
-- 效能: 查詢從 ~750ms 降至 ~184ms (-75%)
-- 前置: 06_gold_kpi_task_completion.sql
-- ========================================

CREATE TABLE IF NOT EXISTS gold.rmv_l5_task_summary (
    -- [維度]
    period_type     Enum8('Day' = 1, 'Week' = 2, 'Month' = 3),
    period_key      String,     -- 'Day': '2025-12-31', 'Week': '2025-W52', 'Month': '2025-12'
    snapshot_date   Date,       -- Day: 原始日期, Week/Month: 該週期最後一天
    sort_order      UInt8,      -- Cube 排序用
    period_name     String,     -- 顯示用: 'Dec.', 'W52', '2025-12-31'
    vx_type         String,
    region          String,
    plant           String,
    factory         String,
    line            String,

    -- [預聚合指標 - 純整數]
    total_qty       UInt64,
    todo_qty        UInt64,
    doing_qty       UInt64,
    done_qty        UInt64,
    doing_done_qty  UInt64,     -- bitmapOr(doing, done) 的去重結果
    acc_qty         UInt64,
    acc_total_qty   UInt64,

    -- [時間戳]
    _refresh_time   DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_refresh_time)
ORDER BY (period_type, vx_type, period_key, region, plant, factory, line)
SETTINGS index_granularity = 8192;
