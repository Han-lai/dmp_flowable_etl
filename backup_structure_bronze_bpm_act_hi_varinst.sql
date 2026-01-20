-- 備份時間: 2026-01-20 10:49:45.480336
-- 原始表格: bronze.bpm_act_hi_varinst

CREATE TABLE bronze.bpm_act_hi_varinst
(
    `ID_` String,
    `REV_` Nullable(Int32),
    `PROC_INST_ID_` Nullable(String),
    `EXECUTION_ID_` Nullable(String),
    `TASK_ID_` Nullable(String),
    `NAME_` String,
    `VAR_TYPE_` Nullable(String),
    `SCOPE_ID_` Nullable(String),
    `SUB_SCOPE_ID_` Nullable(String),
    `SCOPE_TYPE_` Nullable(String),
    `BYTEARRAY_ID_` Nullable(String),
    `DOUBLE_` Nullable(Float64),
    `LONG_` Nullable(Decimal(19, 0)),
    `TEXT_` Nullable(String),
    `TEXT2_` Nullable(String),
    `CREATE_TIME_` DateTime64(6),
    `LAST_UPDATED_TIME_` Nullable(DateTime64(7)),
    `META_INFO_` Nullable(String),
    `_sync_time` DateTime64(3)
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY ID_
SETTINGS index_granularity = 8192;
