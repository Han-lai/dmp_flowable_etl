-- 重建前備份: 2026-01-20 11:02:56.076387
-- 原表格: bronze.common_process_role_group_mapping

CREATE TABLE bronze.common_process_role_group_mapping
(
    `ID` Int32,
    `Plant` String,
    `GroupCode` String,
    `RoleId` String,
    `LinkSupervisor` String,
    `RoleExchangedBy` String,
    `Updater` Nullable(String),
    `UpdateDatetime` DateTime64(6),
    `UpdateCount` Int32,
    `Creator` Nullable(String),
    `CreateDatetime` DateTime64(6),
    `Factory` String
)
ENGINE = MergeTree
ORDER BY tuple()
SETTINGS index_granularity = 8192;
