-- 備份時間: 2026-01-20 10:49:46.445713
-- 原始表格: bronze.common_process_role_group

CREATE TABLE bronze.common_process_role_group
(
    `GroupCode` String,
    `GroupName` String,
    `Updater` String,
    `UpdateDatetime` DateTime64(3),
    `UpdateCount` Int32,
    `Creator` Nullable(String),
    `CreateDatetime` DateTime64(6),
    `DisplayOrder` Nullable(Int32)
)
ENGINE = MergeTree
ORDER BY tuple()
SETTINGS index_granularity = 8192;
