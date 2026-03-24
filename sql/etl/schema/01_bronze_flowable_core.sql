-- ========================================
-- 步驟 1: Bronze Layer - Flowable 核心表
-- 內容: TaskInst, VarInst, ProcInst, ProcDef, IdentityLink
-- ========================================

-- 1. bpm_act_hi_taskinst (Optimized for 6GB RAM Sync)
-- DROP TABLE IF EXISTS bronze.bpm_act_hi_taskinst;
CREATE TABLE IF NOT EXISTS bronze.bpm_act_hi_taskinst
(
    ID_ String,
    REV_ Nullable(Int32),
    PROC_DEF_ID_ Nullable(String),
    TASK_DEF_KEY_ Nullable(String),
    PROC_INST_ID_ Nullable(String),
    EXECUTION_ID_ Nullable(String),
    NAME_ Nullable(String),
    ASSIGNEE_ Nullable(String),
    START_TIME_ DateTime64(3),
    CLAIM_TIME_ Nullable(DateTime64(3)),
    END_TIME_ Nullable(DateTime64(3)),
    DURATION_ Nullable(Int64),
    DELETE_REASON_ Nullable(String),
    LAST_UPDATED_TIME_ DateTime64(3),
    _batch_id String,
    _extracted_at DateTime64(3),
    _sync_version UInt64 DEFAULT 1
)
ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (ID_, START_TIME_);

-- 2. bpm_act_hi_varinst (Optimized for 6GB RAM Sync - No BYTEARRAY_)
-- DROP TABLE IF EXISTS bronze.bpm_act_hi_varinst;
CREATE TABLE IF NOT EXISTS bronze.bpm_act_hi_varinst
(
    PROC_INST_ID_ String,
    TASK_ID_ Nullable(String),
    NAME_ String,
    TEXT_ Nullable(String),
    REV_ Nullable(Int32),
    LONG_ Nullable(Int64),
    CREATE_TIME_ DateTime64(3),
    _batch_id String,
    _extracted_at DateTime64(3),
    _sync_version UInt64 DEFAULT 1
)
ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (PROC_INST_ID_, NAME_, CREATE_TIME_);

-- 3. bpm_act_hi_procinst (流程實例歷史 - 暫維持原樣)
-- DROP TABLE IF EXISTS bronze.bpm_act_hi_procinst;
CREATE TABLE IF NOT EXISTS bronze.bpm_act_hi_procinst
(
    `ID_` String,
    `REV_` Nullable(Int32),
    `PROC_INST_ID_` Nullable(String),
    `BUSINESS_KEY_` Nullable(String),
    `PROC_DEF_ID_` Nullable(String),
    `START_TIME_` DateTime64(3),
    `END_TIME_` Nullable(DateTime64(3)),
    `DURATION_` Nullable(Decimal(18, 3)),
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
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
)
ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY ID_
TTL toDate(START_TIME_) + toIntervalYear(1)
SETTINGS allow_nullable_key = 1;

-- 4. bpm_act_re_procdef (流程定義)
-- DROP TABLE IF EXISTS bronze.bpm_act_re_procdef;
CREATE TABLE IF NOT EXISTS bronze.bpm_act_re_procdef
(
    `ID_` String,
    `REV_` Nullable(Int32),
    `CATEGORY_` Nullable(String),
    `NAME_` Nullable(String),
    `KEY_` Nullable(String),
    `VERSION_` Nullable(Int32),
    `DEPLOYMENT_ID_` Nullable(String),
    `RESOURCE_NAME_` Nullable(String),
    `DGRM_RESOURCE_NAME_` Nullable(String),
    `DESCRIPTION_` Nullable(String),
    `HAS_START_FORM_KEY_` Nullable(UInt8),
    `HAS_GRAPHICAL_NOTATION_` Nullable(UInt8),
    `SUSPENSION_STATE_` Nullable(Int32),
    `TENANT_ID_` Nullable(String),
    `ENGINE_VERSION_` Nullable(String),
    `DERIVED_FROM_` Nullable(String),
    `DERIVED_FROM_ROOT_` Nullable(String),
    `DERIVED_VERSION_` Nullable(Int32),
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
)
ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY ID_
SETTINGS allow_nullable_key = 1;

-- 5. bpm_act_hi_identitylink (身分連結 - 已優化)
-- DROP TABLE IF EXISTS bronze.bpm_act_hi_identitylink;
CREATE TABLE IF NOT EXISTS bronze.bpm_act_hi_identitylink (
    `USER_ID_` Nullable(String),
    `TYPE_` Nullable(String),
    `TASK_ID_` Nullable(String),
    `CREATE_TIME_` Nullable(DateTime64(3)),
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (TASK_ID_, USER_ID_, TYPE_)
TTL toDate(_extracted_at) + INTERVAL 1 YEAR
SETTINGS allow_nullable_key = 1;
