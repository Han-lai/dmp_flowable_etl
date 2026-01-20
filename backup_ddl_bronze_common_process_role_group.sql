-- 重建前備份: 2026-01-20 11:02:52.980817
-- 原表格: bronze.common_process_role_group

CREATE TABLE bronze.common_process_role_group
(
    `GroupCode` String,
    `GroupName` String,
    `Updater` String,
    `UpdateDatetime` DateTime64(6),
    `UpdateCount` Int32,
    `Creator` Nullable(String),
    `CreateDatetime` DateTime64(6),
    `DisplayOrder` Nullable(Int32)
)
ENGINE = MergeTree
ORDER BY tuple()
SETTINGS index_granularity = 8192;
