-- 備份時間: 2026-01-20 10:49:45.963973
-- 原始表格: bronze.common_dmp_function_client_mapping

CREATE TABLE bronze.common_dmp_function_client_mapping
(
    `ID` Int32,
    `Region` String,
    `Plant` String,
    `Logsys` Nullable(String),
    `Updater` Nullable(String),
    `UpdateDatetime` Nullable(DateTime64(3)),
    `UpdateCount` Int32,
    `Creator` Nullable(String),
    `CreateDatetime` DateTime64(6)
)
ENGINE = MergeTree
ORDER BY tuple()
SETTINGS index_granularity = 8192;
