-- ============================================
-- APP_SRV_BPM (Flowable) Bronze 表建立腳本
-- ============================================

-- 1. ACT_HI_PROCINST - 流程實例歷史（主表）
CREATE TABLE IF NOT EXISTS bronze.bpm_act_hi_procinst
(
    ID_ String,
    REV_ Nullable(Int32),
    PROC_INST_ID_ String,
    BUSINESS_KEY_ Nullable(String),
    PROC_DEF_ID_ String,
    START_TIME_ DateTime,
    END_TIME_ Nullable(DateTime),
    DURATION_ Nullable(Decimal(38, 0)),
    START_USER_ID_ Nullable(String),
    START_ACT_ID_ Nullable(String),
    END_ACT_ID_ Nullable(String),
    SUPER_PROCESS_INSTANCE_ID_ Nullable(String),
    DELETE_REASON_ Nullable(String),
    TENANT_ID_ Nullable(String),
    NAME_ Nullable(String),
    CALLBACK_ID_ Nullable(String),
    CALLBACK_TYPE_ Nullable(String),
    REFERENCE_ID_ Nullable(String),
    REFERENCE_TYPE_ Nullable(String),
    PROPAGATED_STAGE_INST_ID_ Nullable(String),
    BUSINESS_STATUS_ Nullable(String),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_BPM',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
PARTITION BY toYYYYMM(START_TIME_)
ORDER BY (PROC_DEF_ID_, START_TIME_, ID_)
SETTINGS index_granularity = 8192;

-- 2. ACT_HI_TASKINST - 任務實例歷史（事件表）
CREATE TABLE IF NOT EXISTS bronze.bpm_act_hi_taskinst
(
    ID_ String,
    REV_ Nullable(Int32),
    PROC_DEF_ID_ Nullable(String),
    TASK_DEF_ID_ Nullable(String),
    TASK_DEF_KEY_ Nullable(String),
    PROC_INST_ID_ Nullable(String),
    EXECUTION_ID_ Nullable(String),
    SCOPE_ID_ Nullable(String),
    SUB_SCOPE_ID_ Nullable(String),
    SCOPE_TYPE_ Nullable(String),
    SCOPE_DEFINITION_ID_ Nullable(String),
    PROPAGATED_STAGE_INST_ID_ Nullable(String),
    NAME_ Nullable(String),
    PARENT_TASK_ID_ Nullable(String),
    DESCRIPTION_ Nullable(String),
    OWNER_ Nullable(String),
    ASSIGNEE_ Nullable(String),
    START_TIME_ DateTime,
    CLAIM_TIME_ Nullable(DateTime),
    END_TIME_ Nullable(DateTime),
    DURATION_ Nullable(Decimal(38, 0)),
    DELETE_REASON_ Nullable(String),
    PRIORITY_ Nullable(Int32),
    DUE_DATE_ Nullable(DateTime),
    FORM_KEY_ Nullable(String),
    CATEGORY_ Nullable(String),
    TENANT_ID_ Nullable(String),
    LAST_UPDATED_TIME_ Nullable(DateTime64(7)),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_BPM',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
PARTITION BY toYYYYMM(START_TIME_)
ORDER BY (PROC_INST_ID_, START_TIME_, ID_)
SETTINGS index_granularity = 8192;


-- 3. ACT_HI_IDENTITYLINK - 任務參與者歷史（關聯表）
CREATE TABLE IF NOT EXISTS bronze.bpm_act_hi_identitylink
(
    ID_ String,
    GROUP_ID_ Nullable(String),
    TYPE_ Nullable(String),
    USER_ID_ Nullable(String),
    TASK_ID_ Nullable(String),
    CREATE_TIME_ Nullable(DateTime),
    PROC_INST_ID_ Nullable(String),
    SCOPE_ID_ Nullable(String),
    SUB_SCOPE_ID_ Nullable(String),
    SCOPE_TYPE_ Nullable(String),
    SCOPE_DEFINITION_ID_ Nullable(String),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_BPM',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
PARTITION BY toYYYYMM(CREATE_TIME_)
ORDER BY (PROC_INST_ID_, TASK_ID_, ID_)
SETTINGS index_granularity = 8192;

-- 4. ACT_HI_VARINST - 流程變數歷史（事件表）
CREATE TABLE IF NOT EXISTS bronze.bpm_act_hi_varinst
(
    ID_ String,
    REV_ Nullable(Int32),
    PROC_INST_ID_ Nullable(String),
    EXECUTION_ID_ Nullable(String),
    TASK_ID_ Nullable(String),
    NAME_ String,
    VAR_TYPE_ Nullable(String),
    SCOPE_ID_ Nullable(String),
    SUB_SCOPE_ID_ Nullable(String),
    SCOPE_TYPE_ Nullable(String),
    BYTEARRAY_ID_ Nullable(String),
    DOUBLE_ Nullable(Float64),
    LONG_ Nullable(Decimal(38, 0)),
    TEXT_ Nullable(String),
    TEXT2_ Nullable(String),
    CREATE_TIME_ Nullable(DateTime),
    LAST_UPDATED_TIME_ Nullable(DateTime64(7)),
    META_INFO_ Nullable(String),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_BPM',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
PARTITION BY toYYYYMM(CREATE_TIME_)
ORDER BY (PROC_INST_ID_, NAME_, ID_)
SETTINGS index_granularity = 8192;

-- 5. ACT_RE_PROCDEF - 流程定義（設定表）
CREATE TABLE IF NOT EXISTS bronze.bpm_act_re_procdef
(
    ID_ String,
    REV_ Nullable(Int32),
    CATEGORY_ Nullable(String),
    NAME_ Nullable(String),
    KEY_ String,
    VERSION_ Int32,
    DEPLOYMENT_ID_ Nullable(String),
    RESOURCE_NAME_ Nullable(String),
    DGRM_RESOURCE_NAME_ Nullable(String),
    DESCRIPTION_ Nullable(String),
    HAS_START_FORM_KEY_ Nullable(UInt8),
    HAS_GRAPHICAL_NOTATION_ Nullable(UInt8),
    SUSPENSION_STATE_ Nullable(UInt8),
    TENANT_ID_ Nullable(String),
    DERIVED_FROM_ Nullable(String),
    DERIVED_FROM_ROOT_ Nullable(String),
    DERIVED_VERSION_ Int32,
    ENGINE_VERSION_ Nullable(String),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_BPM',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (KEY_, VERSION_, ID_)
SETTINGS index_granularity = 8192;
