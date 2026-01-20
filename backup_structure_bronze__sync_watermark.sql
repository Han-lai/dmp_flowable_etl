-- 備份時間: 2026-01-20 10:49:42.699337
-- 原始表格: bronze._sync_watermark

CREATE TABLE bronze._sync_watermark
(
    `table_name` String,
    `last_sync_time` DateTime64(6),
    `sync_time` DateTime64(3),
    `row_count` UInt64
)
ENGINE = ReplacingMergeTree(sync_time)
ORDER BY table_name
SETTINGS index_granularity = 8192;
