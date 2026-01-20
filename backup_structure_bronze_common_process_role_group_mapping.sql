-- 備份時間: 2026-01-20 10:49:46.525859
-- 原始表格: bronze.common_process_role_group_mapping

CREATE TABLE bronze.common_process_role_group_mapping
(
    `ID` Int32,
    `Plant` String,
    `GroupCode` String,
    `RoleId` String,
    `LinkSupervisor` String,
    `RoleExchangedBy` String,
    `Updater` Nullable(String),
    `UpdateDatetime` Nullable(DateTime64(3)),
    `UpdateCount` Int32,
    `Creator` Nullable(String),
    `CreateDatetime` DateTime64(6),
    `Factory` String
)
ENGINE = MergeTree
ORDER BY tuple()
SETTINGS index_granularity = 8192;
