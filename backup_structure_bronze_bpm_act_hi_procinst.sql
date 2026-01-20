-- 備份時間: 2026-01-20 10:49:43.195405
-- 原始表格: bronze.bpm_act_hi_procinst

CREATE TABLE bronze.bpm_act_hi_procinst
(
    `ID_` String,
    `REV_` Nullable(Int32),
    `PROC_INST_ID_` String,
    `BUSINESS_KEY_` Nullable(String),
    `PROC_DEF_ID_` String,
    `START_TIME_` DateTime64(6),
    `END_TIME_` DateTime64(6),
    `DURATION_` Nullable(Decimal(19, 0)),
    `START_USER_ID_` Nullable(String),
    `START_ACT_ID_` Nullable(String),
    `END_ACT_ID_` Nullable(String),
    `SUPER_PROCESS_INSTANCE_ID_` Nullable(String),
    `DELETE_REASON_` Nullable(String),
    `TENANT_ID_` Nullable(String),
    `NAME_` Nullable(String),
    `CALLBACK_ID_` Nullable(String),
    `CALLBACK_TYPE_` Nullable(String),
    `REFERENCE_ID_` Nullable(String),
    `REFERENCE_TYPE_` Nullable(String),
    `PROPAGATED_STAGE_INST_ID_` Nullable(String),
    `BUSINESS_STATUS_` Nullable(String),
    `_sync_time` DateTime64(3)
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY ID_
SETTINGS index_granularity = 8192;
