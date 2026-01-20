-- 備份時間: 2026-01-20 10:49:42.871455
-- 原始表格: bronze.bpm_act_hi_identitylink

CREATE TABLE bronze.bpm_act_hi_identitylink
(
    `ID_` String,
    `GROUP_ID_` Nullable(String),
    `TYPE_` Nullable(String),
    `USER_ID_` Nullable(String),
    `TASK_ID_` Nullable(String),
    `CREATE_TIME_` DateTime64(6),
    `PROC_INST_ID_` Nullable(String),
    `SCOPE_ID_` Nullable(String),
    `SUB_SCOPE_ID_` Nullable(String),
    `SCOPE_TYPE_` Nullable(String),
    `SCOPE_DEFINITION_ID_` Nullable(String),
    `_sync_time` DateTime64(3)
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY ID_
SETTINGS index_granularity = 8192;
