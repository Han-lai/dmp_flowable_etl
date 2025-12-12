-- ============================================
-- Incremental Load 同步腳本
-- 使用時間戳欄位進行增量同步
-- ============================================

-- 設定 batch_id
SET param_batch_id = toString(generateUUIDv4());

-- ============================================
-- 1. ACT_HI_TASKINST - 增量同步（使用 LAST_UPDATED_TIME_）
-- ============================================
-- 取得上次同步時間
WITH last_sync AS (
    SELECT coalesce(max(last_sync_value), '1970-01-01 00:00:00') as last_time
    FROM bronze._sync_log
    WHERE source_db = 'APP_SRV_BPM' 
      AND table_name = 'ACT_HI_TASKINST'
      AND status = 'success'
)
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
FROM jdbc('mssql_bpm', 
    concat('SELECT * FROM ACT_HI_TASKINST WHERE LAST_UPDATED_TIME_ > ''', 
           (SELECT last_time FROM last_sync), '''')
);


-- ============================================
-- 2. FlowableTaskStats - 增量同步（使用 LastUpdatedTime）
-- ============================================
INSERT INTO bronze.common_flowable_task_stats
SELECT 
    Id, ProcessInstanceId, ProcessDefinitionKey, ProcessDefinitionName,
    ProcessTeam, Plant, Factory, ProductionArea, Line, ModelName,
    DeliveryArea, ScheduleNumber, MoNumber, SapPlant, SapProductGroup,
    Pallet, TransferNo, QBlockEventId, DefectSn, Time_,
    TaskId, TaskDefinitionKey, TaskName, TaskStatus, TaskBypass,
    TaskAssignee, TaskAssigneeAccount, TaskAssigneeName,
    TaskCreateTime, TaskClaimTime, TaskEndTime,
    TaskDurationMinutes, TaskWorkMinutes, DeleteReason,
    SyncTime, LastUpdatedTime, TaskCreateDate, TaskClaimDate, TaskEndDate,
    now64(3) as _sync_time,
    'APP_SRV_COMMON' as _source_db,
    {batch_id:String} as _batch_id
FROM jdbc('mssql_common', 
    'SELECT * FROM FlowableTaskStats WHERE LastUpdatedTime > DATEADD(hour, -1, GETDATE())'
);

-- ============================================
-- 3. ACT_HI_VARINST - 增量同步（使用 LAST_UPDATED_TIME_）
-- ============================================
INSERT INTO bronze.bpm_act_hi_varinst
SELECT 
    ID_, REV_, PROC_INST_ID_, EXECUTION_ID_, TASK_ID_,
    NAME_, VAR_TYPE_, SCOPE_ID_, SUB_SCOPE_ID_, SCOPE_TYPE_,
    BYTEARRAY_ID_, DOUBLE_, LONG_, TEXT_, TEXT2_,
    CREATE_TIME_, LAST_UPDATED_TIME_, META_INFO_,
    now64(3) as _sync_time,
    'APP_SRV_BPM' as _source_db,
    {batch_id:String} as _batch_id
FROM jdbc('mssql_bpm', 
    'SELECT * FROM ACT_HI_VARINST WHERE LAST_UPDATED_TIME_ > DATEADD(hour, -1, GETDATE())'
);

-- ============================================
-- 4. ACT_HI_IDENTITYLINK - 增量同步（使用 CREATE_TIME_）
-- ============================================
INSERT INTO bronze.bpm_act_hi_identitylink
SELECT 
    ID_, GROUP_ID_, TYPE_, USER_ID_, TASK_ID_,
    CREATE_TIME_, PROC_INST_ID_, SCOPE_ID_, SUB_SCOPE_ID_,
    SCOPE_TYPE_, SCOPE_DEFINITION_ID_,
    now64(3) as _sync_time,
    'APP_SRV_BPM' as _source_db,
    {batch_id:String} as _batch_id
FROM jdbc('mssql_bpm', 
    'SELECT * FROM ACT_HI_IDENTITYLINK WHERE CREATE_TIME_ > DATEADD(hour, -1, GETDATE())'
);

-- ============================================
-- 5. ACT_HI_PROCINST - 增量同步（使用 START_TIME_）
-- ============================================
INSERT INTO bronze.bpm_act_hi_procinst
SELECT 
    ID_, REV_, PROC_INST_ID_, BUSINESS_KEY_, PROC_DEF_ID_,
    START_TIME_, END_TIME_, DURATION_, START_USER_ID_, START_ACT_ID_,
    END_ACT_ID_, SUPER_PROCESS_INSTANCE_ID_, DELETE_REASON_, TENANT_ID_,
    NAME_, CALLBACK_ID_, CALLBACK_TYPE_, REFERENCE_ID_, REFERENCE_TYPE_,
    PROPAGATED_STAGE_INST_ID_, BUSINESS_STATUS_,
    now64(3) as _sync_time,
    'APP_SRV_BPM' as _source_db,
    {batch_id:String} as _batch_id
FROM jdbc('mssql_bpm', 
    'SELECT * FROM ACT_HI_PROCINST WHERE START_TIME_ > DATEADD(hour, -1, GETDATE())'
);
