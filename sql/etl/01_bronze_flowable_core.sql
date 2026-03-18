-- ========================================
-- 步驟 1: Bronze Layer - Flowable 核心表
-- 內容: TaskInst, VarInst, ProcInst
-- ========================================
-- DROP TABLE IF EXISTS bronze.bpm_act_hi_taskinst;

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
    `START_TIME_` DateTime64(3),
    `CLAIM_TIME_` Nullable(DateTime64(3)),
    `END_TIME_` Nullable(DateTime64(3)),
    `DURATION_` Nullable(Decimal(18, 3)),
    `DELETE_REASON_` Nullable(String),
    `PRIORITY_` Nullable(Int32),
    `DUE_DATE_` Nullable(DateTime64(3)),
    `FORM_KEY_` Nullable(String),
    `CATEGORY_` Nullable(String),
    `TENANT_ID_` Nullable(String),
    `LAST_UPDATED_TIME_` Nullable(DateTime64(3)),
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
)
ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY ID_
TTL toDate(START_TIME_) + toIntervalYear(1)
SETTINGS allow_nullable_key = 1;

-- ========================================
-- 2. bpm_act_hi_varinst (變數實例歷史)
-- 來源: APP_SRV_BPM.dbo.ACT_HI_VARINST
-- ========================================
-- DROP TABLE IF EXISTS bronze.bpm_act_hi_varinst;

CREATE TABLE bronze.bpm_act_hi_varinst
(
    `ID_` String,
    `REV_` Nullable(Int32),
    `PROC_INST_ID_` Nullable(String),
    `EXECUTION_ID_` Nullable(String),
    `TASK_ID_` Nullable(String),
    `NAME_` Nullable(String),
    `VAR_TYPE_` Nullable(String),
    `SCOPE_ID_` Nullable(String),
    `SUB_SCOPE_ID_` Nullable(String),
    `SCOPE_TYPE_` Nullable(String),
    `BYTEARRAY_ID_` Nullable(String),
    `DOUBLE_` Nullable(Float64),
    `LONG_` Nullable(Int64),
    `TEXT_` Nullable(String),
    `TEXT2_` Nullable(String),
    `META_INFO_` Nullable(String),
    `CREATE_TIME_` Nullable(DateTime64(3)),
    `LAST_UPDATED_TIME_` Nullable(DateTime64(3)),
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
)
ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY ID_
TTL toDate(_extracted_at) + toIntervalYear(1)
SETTINGS allow_nullable_key = 1;

-- ========================================
-- 3. bpm_act_hi_procinst (流程實例歷史)
-- 來源: APP_SRV_BPM.dbo.ACT_HI_PROCINST
-- ========================================
-- DROP TABLE IF EXISTS bronze.bpm_act_hi_procinst;

CREATE TABLE bronze.bpm_act_hi_procinst
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

-- 驗證表已建立
SELECT 'Tables created:' AS status;
SELECT database, name, engine FROM system.tables 
WHERE database = 'bronze' AND name LIKE 'bpm_act_%'
ORDER BY name;

-- ========================================
-- 4. bpm_act_re_procdef (流程定義)
-- 來源: APP_SRV_BPM.dbo.ACT_RE_PROCDEF
-- ========================================
-- DROP TABLE IF EXISTS bronze.bpm_act_re_procdef;

CREATE TABLE bronze.bpm_act_re_procdef
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

-- ========================================
-- 5. bpm_act_hi_identitylink (身分連結)
-- 來源: APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK
-- ========================================
-- DROP TABLE IF EXISTS bronze.bpm_act_hi_identitylink;

CREATE TABLE bronze.bpm_act_hi_identitylink (
    `ID_` String,
    `GROUP_ID_` Nullable(String),
    `TYPE_` Nullable(String),
    `USER_ID_` Nullable(String),
    `TASK_ID_` Nullable(String),
    `PROC_INST_ID_` Nullable(String),
    `SCOPE_ID_` Nullable(String),
    `SUB_SCOPE_ID_` Nullable(String),
    `SCOPE_TYPE_` Nullable(String),
    `SCOPE_DEFINITION_ID_` Nullable(String),
    `CREATE_TIME_` Nullable(DateTime64(3)),
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY ID_
TTL toDate(_extracted_at) + INTERVAL 1 YEAR
SETTINGS allow_nullable_key = 1;

