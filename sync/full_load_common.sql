-- ============================================
-- APP_SRV_COMMON (DMP) Full Load 同步腳本
-- 使用 JDBC Bridge 從 MSSQL 同步資料到 ClickHouse
-- ============================================

-- 設定 batch_id
SET param_batch_id = toString(generateUUIDv4());

-- ============================================
-- 1. FlowableTaskStats - 任務統計彙總（最大表 73萬筆）
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_COMMON', 'FlowableTaskStats', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.common_flowable_task_stats;

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
FROM jdbc('mssql_common', 'SELECT * FROM FlowableTaskStats');

-- ============================================
-- 2. HR_Employee - 員工主檔（18萬筆）
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_COMMON', 'HR_Employee', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.common_hr_employee;

INSERT INTO bronze.common_hr_employee
SELECT 
    EmpCode, EmpName, DisplayName, UnicodeName, EnglishName,
    FirstName, MiddleName, LastName, ADAccount, ADDomain,
    TerminateDate, Email, ExtNo, DeptCode, DeptCodeLname, DeptCodeEname,
    CostCenterCode, CostCenterLname, SuperiorDeptCode, SuperiorDeptLname,
    SuperiorDeptEname, Supervisor, FactoryCode, FactoryLname, FactoryEname,
    BGID, BGShortName, BUID, BUShortName, CompanyCode, CompanyLname,
    CompanyEname, SAPCompanyCode, AreaID, AreaLname, AreaEname,
    GenderID, GenderLname, GenderEname, Shift, OrgUnitCode,
    OrgUnitLname, OrgUnitEname, OrgUnitMgrEmpNo, JobFamilyCode,
    JobFamilyName, JobFamilyEName, DeptEmpCode, DeptEmpName,
    CostCenterEname, ModifyDate, JobCode,
    now64(3) as _sync_time,
    'APP_SRV_COMMON' as _source_db,
    {batch_id:String} as _batch_id
FROM jdbc('mssql_common', 'SELECT * FROM HR_Employee');

-- ============================================
-- 3. ProcessRoleUserMapping - 角色-員工對應
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_COMMON', 'ProcessRoleUserMapping', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.common_process_role_user_mapping;

INSERT INTO bronze.common_process_role_user_mapping
SELECT 
    ID, RoleId, Plant, Factory, ProductionArea, LineName,
    EmpCode, Updater, UpdateDatetime, UpdateCount, Creator, CreateDatetime,
    now64(3), 'APP_SRV_COMMON', {batch_id:String}
FROM jdbc('mssql_common', 'SELECT * FROM ProcessRoleUserMapping');


-- ============================================
-- 4. ProcessRoleGroup - 角色群組定義
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_COMMON', 'ProcessRoleGroup', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.common_process_role_group;

INSERT INTO bronze.common_process_role_group
SELECT 
    GroupCode, GroupName, Updater, UpdateDatetime, UpdateCount,
    Creator, CreateDatetime, DisplayOrder,
    now64(3), 'APP_SRV_COMMON', {batch_id:String}
FROM jdbc('mssql_common', 'SELECT * FROM ProcessRoleGroup');

-- ============================================
-- 5. ProcessRoleGroupMapping - 角色群組對應
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_COMMON', 'ProcessRoleGroupMapping', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.common_process_role_group_mapping;

INSERT INTO bronze.common_process_role_group_mapping
SELECT 
    ID, Plant, GroupCode, RoleId, LinkSupervisor, RoleExchangedBy,
    Updater, UpdateDatetime, UpdateCount, Creator, CreateDatetime, Factory,
    now64(3), 'APP_SRV_COMMON', {batch_id:String}
FROM jdbc('mssql_common', 'SELECT * FROM ProcessRoleGroupMapping');

-- ============================================
-- 6. EmpNodeRoleMapping - 員工-節點角色
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_COMMON', 'EmpNodeRoleMapping', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.common_emp_node_role_mapping;

INSERT INTO bronze.common_emp_node_role_mapping
SELECT 
    EmpCode, NodeCode, UpdateTime, UpdateEmp, Vx,
    now64(3), 'APP_SRV_COMMON', {batch_id:String}
FROM jdbc('mssql_common', 'SELECT * FROM EmpNodeRoleMapping');

-- ============================================
-- 7. EmpOrgInfoMapping - 員工-組織對應
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_COMMON', 'EmpOrgInfoMapping', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.common_emp_org_info_mapping;

INSERT INTO bronze.common_emp_org_info_mapping
SELECT 
    EmpCode, Plant, MFGFactoryId, UpdateTime, UpdateEmp,
    now64(3), 'APP_SRV_COMMON', {batch_id:String}
FROM jdbc('mssql_common', 'SELECT * FROM EmpOrgInfoMapping');

-- ============================================
-- 8. EmpUserGroupMapping - 員工-群組對應
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_COMMON', 'EmpUserGroupMapping', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.common_emp_user_group_mapping;

INSERT INTO bronze.common_emp_user_group_mapping
SELECT 
    EmpCode, UserGroupId, UpdateTime, UpdateEmp,
    now64(3), 'APP_SRV_COMMON', {batch_id:String}
FROM jdbc('mssql_common', 'SELECT * FROM EmpUserGroupMapping');

-- ============================================
-- 9. UserGroup - 使用者群組定義
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_COMMON', 'UserGroup', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.common_user_group;

INSERT INTO bronze.common_user_group
SELECT 
    UserGroupId, UserGroupName, UserGroupDesc, UpdateTime, UpdateEmp,
    now64(3), 'APP_SRV_COMMON', {batch_id:String}
FROM jdbc('mssql_common', 'SELECT * FROM UserGroup');

-- ============================================
-- 10. DMPFunctionConfig - 功能設定
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_COMMON', 'DMPFunctionConfig', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.common_dmp_function_config;

INSERT INTO bronze.common_dmp_function_config
SELECT 
    ID, FunctionCode, Plant, Factory, ProductionArea, LineName,
    AssignLineFlag, Updater, UpdateDatetime, UpdateCount, Creator, CreateDatetime,
    now64(3), 'APP_SRV_COMMON', {batch_id:String}
FROM jdbc('mssql_common', 'SELECT * FROM DMPFunctionConfig');

-- ============================================
-- 11. DMPFunctionClientMapping - 客戶端對應
-- ============================================
INSERT INTO bronze._sync_log (batch_id, source_db, table_name, sync_type, start_time, status)
VALUES ({batch_id:String}, 'APP_SRV_COMMON', 'DMPFunctionClientMapping', 'full', now64(3), 'running');

TRUNCATE TABLE bronze.common_dmp_function_client_mapping;

INSERT INTO bronze.common_dmp_function_client_mapping
SELECT 
    ID, Region, Plant, Logsys, Updater, UpdateDatetime,
    UpdateCount, Creator, CreateDatetime,
    now64(3), 'APP_SRV_COMMON', {batch_id:String}
FROM jdbc('mssql_common', 'SELECT * FROM DMPFunctionClientMapping');
