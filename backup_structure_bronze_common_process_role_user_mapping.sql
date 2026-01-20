-- 備份時間: 2026-01-20 10:49:46.673302
-- 原始表格: bronze.common_process_role_user_mapping

CREATE TABLE bronze.common_process_role_user_mapping
(
    `ID` Int32,
    `RoleId` String,
    `Plant` String,
    `Factory` Nullable(String),
    `ProductionArea` Nullable(String),
    `LineName` Nullable(String),
    `EmpCode` String,
    `Updater` Nullable(String),
    `UpdateDatetime` Nullable(DateTime64(3)),
    `UpdateCount` Int32,
    `Creator` Nullable(String),
    `CreateDatetime` DateTime64(6)
)
ENGINE = MergeTree
ORDER BY tuple()
SETTINGS index_granularity = 8192;
