-- ============================================
-- APP_SRV_BPM (Flowable) Full Load 同步腳本
-- 使用 JDBC Bridge 從 MSSQL 同步資料到 ClickHouse
-- ============================================

-- 設定 batch_id（每次執行產生新的）
SET param_batch_id = toString(generateUUIDv4());

-- ============================================
-- 1. ACT_HI_PROCINST - 流程實例歷史
-- ============================================
-- 記錄同步開始
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
SELECT 
    {batch_id:String} as batch_id,
    'APP_SRV_BPM' as source_db,
    'ACT_HI_PROCINST' as table_name,
    'full' as sync_type,
    now64(3) as start_time,
    'running' as status;

-- 清空目標表
TRUNCATE TABLE bronze.bpm_act_hi_procinst;

-- 從 MSSQL 同步資料
INSERT INTO bronze.bpm_act_hi_procinst
SELECT 
    ID_,
    REV_,
    PROC_INST_ID_,
    BUSINESS_KEY_,
    PROC_DEF_ID_,
    START_TIME_,
    END_TIME_,
    DURATION_,
    START_USER_ID_,
    START_ACT_ID_,
    END_ACT_ID_,
    SUPER_PROCESS_INSTANCE_ID_,
    DELETE_REASON_,
    TENANT_ID_,
    NAME_,
    CALLBACK_ID_,
    CALLBACK_TYPE_,
    REFERENCE_ID_,
    REFERENCE_TYPE_,
    PROPAGATED_STAGE_INST_ID_,
    BUSINESS_STATUS_,
    now64(3) as _sync_time,
    'APP_SRV_BPM' as _source_db,
    {batch_id:String} as _batch_id
FROM jdbc('mssql_bpm', 'SELECT * FROM ACT_HI_PROCINST');

-- ============================================
-- 2. ACT_HI_TASKINST - 任務實例歷史
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_BPM', 'ACT_HI_TASKINST', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.bpm_act_hi_taskinst;

INSERT INTO bronze.bpm_act_hi_taskinst
SELECT 
    ID_, REV_, PROC_DEF_ID_, TASK_DEF_ID_, TASK_DEF_KEY_,
    PROC_INST_ID_, EXECUTION_ID_, SCOPE_ID_, SUB_SCOPE_ID_, SCOPE_TYPE_,
    SCOPE_DEFINITION_ID_, PROPAGATED_STAGE_INST_ID_, NAME_, PARENT_TASK_ID_,
    DESCRIPTION_, OWNER_, ASSIGNEE_, START_TIME_, CLAIM_TIME_, END_TIME_,
    DURATION_, DELETE_REASON_, PRIORITY_, DUE_DATE_, FORM_KEY_,
    CATEGORY_, TENANT_ID_, LAST_UPDATED_TIME_,
    now64(3) as _sync_time,
    'APP_SRV_BPM' as _source_db,
    {batch_id:String} as _batch_id
FROM jdbc('mssql_bpm', 'SELECT * FROM ACT_HI_TASKINST');

-- ============================================
-- 3. ACT_HI_IDENTITYLINK - 任務參與者歷史
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_BPM', 'ACT_HI_IDENTITYLINK', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.bpm_act_hi_identitylink;

INSERT INTO bronze.bpm_act_hi_identitylink
SELECT 
    ID_, GROUP_ID_, TYPE_, USER_ID_, TASK_ID_,
    CREATE_TIME_, PROC_INST_ID_, SCOPE_ID_, SUB_SCOPE_ID_,
    SCOPE_TYPE_, SCOPE_DEFINITION_ID_,
    now64(3) as _sync_time,
    'APP_SRV_BPM' as _source_db,
    {batch_id:String} as _batch_id
FROM jdbc('mssql_bpm', 'SELECT * FROM ACT_HI_IDENTITYLINK');

-- ============================================
-- 4. ACT_HI_VARINST - 流程變數歷史
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_BPM', 'ACT_HI_VARINST', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.bpm_act_hi_varinst;

INSERT INTO bronze.bpm_act_hi_varinst
SELECT 
    ID_, REV_, PROC_INST_ID_, EXECUTION_ID_, TASK_ID_,
    NAME_, VAR_TYPE_, SCOPE_ID_, SUB_SCOPE_ID_, SCOPE_TYPE_,
    BYTEARRAY_ID_, DOUBLE_, LONG_, TEXT_, TEXT2_,
    CREATE_TIME_, LAST_UPDATED_TIME_, META_INFO_,
    now64(3) as _sync_time,
    'APP_SRV_BPM' as _source_db,
    {batch_id:String} as _batch_id
FROM jdbc('mssql_bpm', 'SELECT * FROM ACT_HI_VARINST');

-- ============================================
-- 5. ACT_RE_PROCDEF - 流程定義
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_BPM', 'ACT_RE_PROCDEF', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.bpm_act_re_procdef;

INSERT INTO bronze.bpm_act_re_procdef
SELECT 
    ID_, REV_, CATEGORY_, NAME_, KEY_, VERSION_,
    DEPLOYMENT_ID_, RESOURCE_NAME_, DGRM_RESOURCE_NAME_,
    DESCRIPTION_, HAS_START_FORM_KEY_, HAS_GRAPHICAL_NOTATION_,
    SUSPENSION_STATE_, TENANT_ID_, DERIVED_FROM_,
    DERIVED_FROM_ROOT_, DERIVED_VERSION_, ENGINE_VERSION_,
    now64(3) as _sync_time,
    'APP_SRV_BPM' as _source_db,
    {batch_id:String} as _batch_id
FROM jdbc('mssql_bpm', 'SELECT * FROM ACT_RE_PROCDEF');
