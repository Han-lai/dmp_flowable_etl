-- ============================================
-- APP_SRV_COMMON (DMP) Bronze 表建立腳本
-- ============================================

-- 1. FlowableTaskStats - 任務統計彙總（最重要的分析表）
CREATE TABLE IF NOT EXISTS bronze.common_flowable_task_stats
(
    Id Decimal(38, 0),
    ProcessInstanceId Nullable(String),
    ProcessDefinitionKey Nullable(String),
    ProcessDefinitionName Nullable(String),
    ProcessTeam Nullable(String),
    Plant Nullable(String),
    Factory Nullable(String),
    ProductionArea Nullable(String),
    Line Nullable(String),
    ModelName Nullable(String),
    DeliveryArea Nullable(String),
    ScheduleNumber Nullable(String),
    MoNumber Nullable(String),
    SapPlant Nullable(String),
    SapProductGroup Nullable(String),
    Pallet Nullable(String),
    TransferNo Nullable(String),
    QBlockEventId Nullable(String),
    DefectSn Nullable(String),
    Time_ Nullable(String),
    TaskId Nullable(String),
    TaskDefinitionKey Nullable(String),
    TaskName Nullable(String),
    TaskStatus Nullable(String),
    TaskBypass Nullable(String),
    TaskAssignee Nullable(String),
    TaskAssigneeAccount Nullable(String),
    TaskAssigneeName Nullable(String),
    TaskCreateTime Nullable(DateTime64(7)),
    TaskClaimTime Nullable(DateTime64(7)),
    TaskEndTime Nullable(DateTime64(7)),
    TaskDurationMinutes Nullable(Float64),
    TaskWorkMinutes Nullable(Float64),
    DeleteReason Nullable(String),
    SyncTime Nullable(DateTime64(7)),
    LastUpdatedTime Nullable(DateTime64(7)),
    TaskCreateDate Nullable(Date),
    TaskClaimDate Nullable(Date),
    TaskEndDate Nullable(Date),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_COMMON',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
PARTITION BY toYYYYMM(TaskCreateDate)
ORDER BY (TaskId)
SETTINGS index_granularity = 8192;

-- 2. HR_Employee - 員工主檔（維度表）
CREATE TABLE IF NOT EXISTS bronze.common_hr_employee
(
    EmpCode String,
    EmpName Nullable(String),
    DisplayName Nullable(String),
    UnicodeName Nullable(String),
    EnglishName Nullable(String),
    FirstName Nullable(String),
    MiddleName Nullable(String),
    LastName Nullable(String),
    ADAccount Nullable(String),
    ADDomain Nullable(String),
    TerminateDate Nullable(DateTime),
    Email Nullable(String),
    ExtNo Nullable(String),
    DeptCode Nullable(String),
    DeptCodeLname Nullable(String),
    DeptCodeEname Nullable(String),
    CostCenterCode Nullable(String),
    CostCenterLname Nullable(String),
    SuperiorDeptCode Nullable(String),
    SuperiorDeptLname Nullable(String),
    SuperiorDeptEname Nullable(String),
    Supervisor Nullable(String),
    FactoryCode Nullable(String),
    FactoryLname Nullable(String),
    FactoryEname Nullable(String),
    BGID Nullable(Int32),
    BGShortName Nullable(String),
    BUID Nullable(Int32),
    BUShortName Nullable(String),
    CompanyCode Nullable(String),
    CompanyLname Nullable(String),
    CompanyEname Nullable(String),
    SAPCompanyCode Nullable(String),
    AreaID Nullable(String),
    AreaLname Nullable(String),
    AreaEname Nullable(String),
    GenderID Nullable(UInt8),
    GenderLname Nullable(String),
    GenderEname Nullable(String),
    Shift Nullable(String),
    OrgUnitCode Nullable(String),
    OrgUnitLname Nullable(String),
    OrgUnitEname Nullable(String),
    OrgUnitMgrEmpNo Nullable(String),
    JobFamilyCode Nullable(String),
    JobFamilyName Nullable(String),
    JobFamilyEName Nullable(String),
    DeptEmpCode Nullable(String),
    DeptEmpName Nullable(String),
    CostCenterEname Nullable(String),
    ModifyDate Nullable(DateTime),
    JobCode Nullable(String),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_COMMON',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (EmpCode)
SETTINGS index_granularity = 8192;


-- 3. ProcessRoleUserMapping - 角色-員工對應（關聯表）
CREATE TABLE IF NOT EXISTS bronze.common_process_role_user_mapping
(
    ID Int32,
    RoleId String,
    Plant String,
    Factory Nullable(String),
    ProductionArea Nullable(String),
    LineName Nullable(String),
    EmpCode String,
    Updater Nullable(String),
    UpdateDatetime Nullable(DateTime),
    UpdateCount Int32,
    Creator Nullable(String),
    CreateDatetime Nullable(DateTime),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_COMMON',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (ID)
SETTINGS index_granularity = 8192;

-- 4. ProcessRoleGroup - 角色群組定義（設定表）
CREATE TABLE IF NOT EXISTS bronze.common_process_role_group
(
    GroupCode String,
    GroupName String,
    Updater String,
    UpdateDatetime DateTime,
    UpdateCount Int32,
    Creator Nullable(String),
    CreateDatetime Nullable(DateTime),
    DisplayOrder Nullable(Int32),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_COMMON',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (GroupCode)
SETTINGS index_granularity = 8192;

-- 5. ProcessRoleGroupMapping - 角色群組對應（關聯表）
CREATE TABLE IF NOT EXISTS bronze.common_process_role_group_mapping
(
    ID Int32,
    Plant String,
    GroupCode String,
    RoleId String,
    LinkSupervisor String,
    RoleExchangedBy String,
    Updater Nullable(String),
    UpdateDatetime Nullable(DateTime),
    UpdateCount Int32,
    Creator Nullable(String),
    CreateDatetime Nullable(DateTime),
    Factory String,
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_COMMON',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (ID)
SETTINGS index_granularity = 8192;

-- 6. EmpNodeRoleMapping - 員工-節點角色（關聯表）
CREATE TABLE IF NOT EXISTS bronze.common_emp_node_role_mapping
(
    EmpCode String,
    NodeCode String,
    UpdateTime DateTime,
    UpdateEmp String,
    Vx String,
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_COMMON',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (EmpCode, NodeCode, Vx)
SETTINGS index_granularity = 8192;

-- 7. EmpOrgInfoMapping - 員工-組織對應（關聯表）
CREATE TABLE IF NOT EXISTS bronze.common_emp_org_info_mapping
(
    EmpCode String,
    Plant String,
    MFGFactoryId String,
    UpdateTime DateTime,
    UpdateEmp String,
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_COMMON',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (EmpCode, MFGFactoryId, Plant)
SETTINGS index_granularity = 8192;

-- 8. EmpUserGroupMapping - 員工-群組對應（關聯表）
CREATE TABLE IF NOT EXISTS bronze.common_emp_user_group_mapping
(
    EmpCode String,
    UserGroupId Int32,
    UpdateTime DateTime,
    UpdateEmp String,
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_COMMON',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (EmpCode, UserGroupId)
SETTINGS index_granularity = 8192;

-- 9. UserGroup - 使用者群組定義（設定表）
CREATE TABLE IF NOT EXISTS bronze.common_user_group
(
    UserGroupId Nullable(Int32),
    UserGroupName Nullable(String),
    UserGroupDesc Nullable(String),
    UpdateTime Nullable(DateTime),
    UpdateEmp Nullable(String),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_COMMON',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (UserGroupId)
SETTINGS index_granularity = 8192;

-- 10. DMPFunctionConfig - 功能設定（設定表）
CREATE TABLE IF NOT EXISTS bronze.common_dmp_function_config
(
    ID Int32,
    FunctionCode String,
    Plant String,
    Factory Nullable(String),
    ProductionArea Nullable(String),
    LineName Nullable(String),
    AssignLineFlag String,
    Updater Nullable(String),
    UpdateDatetime Nullable(DateTime),
    UpdateCount Nullable(Int32),
    Creator Nullable(String),
    CreateDatetime Nullable(DateTime),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_COMMON',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (ID)
SETTINGS index_granularity = 8192;

-- 11. DMPFunctionClientMapping - 客戶端對應（設定表）
CREATE TABLE IF NOT EXISTS bronze.common_dmp_function_client_mapping
(
    ID Int32,
    Region String,
    Plant String,
    Logsys Nullable(String),
    Updater Nullable(String),
    UpdateDatetime Nullable(DateTime),
    UpdateCount Int32,
    Creator Nullable(String),
    CreateDatetime Nullable(DateTime),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3),
    _source_db LowCardinality(String) DEFAULT 'APP_SRV_COMMON',
    _batch_id String
)
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (ID)
SETTINGS index_granularity = 8192;
