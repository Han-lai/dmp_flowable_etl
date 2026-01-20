-- 備份時間: 2026-01-20 10:49:44.722638
-- 原始表格: bronze.bpm_act_hi_taskinst

CREATE TABLE bronze.bpm_act_hi_taskinst
(
    `ID_` String,
    `REV_` Nullable(Int32),
    `PROC_DEF_ID_` Nullable(String),
    `TASK_DEF_ID_` Nullable(String),
    `TASK_DEF_KEY_` Nullable(String),
    `PROC_INST_ID_` Nullable(String),
    `EXECUTION_ID_` Nullable(String),
    `SCOPE_ID_` Nullable(String),
    `SUB_SCOPE_ID_` Nullable(String),
    `SCOPE_TYPE_` Nullable(String),
    `SCOPE_DEFINITION_ID_` Nullable(String),
    `PROPAGATED_STAGE_INST_ID_` Nullable(String),
    `NAME_` Nullable(String),
    `PARENT_TASK_ID_` Nullable(String),
    `DESCRIPTION_` Nullable(String),
    `OWNER_` Nullable(String),
    `ASSIGNEE_` Nullable(String),
    `START_TIME_` DateTime64(6),
    `CLAIM_TIME_` DateTime64(6),
    `END_TIME_` DateTime64(6),
    `DURATION_` Nullable(Decimal(19, 0)),
    `DELETE_REASON_` Nullable(String),
    `PRIORITY_` Nullable(Int32),
    `DUE_DATE_` DateTime64(6),
    `FORM_KEY_` Nullable(String),
    `CATEGORY_` Nullable(String),
    `TENANT_ID_` Nullable(String),
    `LAST_UPDATED_TIME_` Nullable(DateTime64(7)),
    `_sync_time` DateTime64(3)
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY ID_
SETTINGS index_granularity = 8192;
