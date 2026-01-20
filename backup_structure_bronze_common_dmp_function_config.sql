-- 備份時間: 2026-01-20 10:49:46.077910
-- 原始表格: bronze.common_dmp_function_config

CREATE TABLE bronze.common_dmp_function_config
(
    `ID` Int32,
    `FunctionCode` String,
    `Plant` String,
    `Factory` Nullable(String),
    `ProductionArea` Nullable(String),
    `LineName` Nullable(String),
    `AssignLineFlag` String,
    `Updater` Nullable(String),
    `UpdateDatetime` Nullable(DateTime64(3)),
    `UpdateCount` Nullable(Int32),
    `Creator` Nullable(String),
    `CreateDatetime` DateTime64(6)
)
ENGINE = MergeTree
ORDER BY tuple()
SETTINGS index_granularity = 8192;
