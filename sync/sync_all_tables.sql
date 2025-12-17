-- ============================================
-- 同步全部 16 張表到 ClickHouse Bronze 層
-- 使用 CREATE TABLE AS SELECT 一步完成建表+同步
-- ============================================

-- 確認 bronze database 存在
CREATE DATABASE IF NOT EXISTS bronze;

-- ============================================
-- APP_SRV_BPM (5 張表)
-- ============================================

-- 1. ACT_HI_PROCINST（流程實例歷史）
DROP TABLE IF EXISTS bronze.bpm_act_hi_procinst;
CREATE TABLE bronze.bpm_act_hi_procinst
ENGINE = MergeTree()
ORDER BY (PROC_DEF_ID_, START_TIME_, ID_)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST');

-- 2. ACT_HI_TASKINST（任務實例歷史）
DROP TABLE IF EXISTS bronze.bpm_act_hi_taskinst;
CREATE TABLE bronze.bpm_act_hi_taskinst
ENGINE = MergeTree()
ORDER BY (PROC_INST_ID_, START_TIME_, ID_)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST');

-- 3. ACT_HI_IDENTITYLINK（任務參與者歷史）
DROP TABLE IF EXISTS bronze.bpm_act_hi_identitylink;
CREATE TABLE bronze.bpm_act_hi_identitylink
ENGINE = MergeTree()
ORDER BY (PROC_INST_ID_, TASK_ID_, ID_)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK');

-- 4. ACT_HI_VARINST（流程變數歷史）
DROP TABLE IF EXISTS bronze.bpm_act_hi_varinst;
CREATE TABLE bronze.bpm_act_hi_varinst
ENGINE = MergeTree()
ORDER BY (PROC_INST_ID_, NAME_, ID_)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_VARINST');

-- 5. ACT_RE_PROCDEF（流程定義）
DROP TABLE IF EXISTS bronze.bpm_act_re_procdef;
CREATE TABLE bronze.bpm_act_re_procdef
ENGINE = MergeTree()
ORDER BY (KEY_, VERSION_, ID_)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_RE_PROCDEF');

-- ============================================
-- APP_SRV_COMMON (11 張表)
-- ============================================

-- 6. FlowableTaskStats（任務統計彙總）
DROP TABLE IF EXISTS bronze.common_flowable_task_stats;
CREATE TABLE bronze.common_flowable_task_stats
ENGINE = MergeTree()
ORDER BY (TaskId, Id)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.FlowableTaskStats');

-- 7. HR_Employee（員工主檔）
DROP TABLE IF EXISTS bronze.common_hr_employee;
CREATE TABLE bronze.common_hr_employee
ENGINE = MergeTree()
ORDER BY EmpCode
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.HR_Employee');

-- 8. ProcessRoleUserMapping（角色-員工對應）
DROP TABLE IF EXISTS bronze.common_process_role_user_mapping;
CREATE TABLE bronze.common_process_role_user_mapping
ENGINE = MergeTree()
ORDER BY (EmpCode, RoleCode)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping');

-- 9. ProcessRoleGroup（角色群組定義）
DROP TABLE IF EXISTS bronze.common_process_role_group;
CREATE TABLE bronze.common_process_role_group
ENGINE = MergeTree()
ORDER BY GroupCode
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.ProcessRoleGroup');

-- 10. ProcessRoleGroupMapping（角色群組對應）
DROP TABLE IF EXISTS bronze.common_process_role_group_mapping;
CREATE TABLE bronze.common_process_role_group_mapping
ENGINE = MergeTree()
ORDER BY (GroupCode, RoleCode)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.ProcessRoleGroupMapping');

-- 11. EmpNodeRoleMapping（員工-節點角色）
DROP TABLE IF EXISTS bronze.common_emp_node_role_mapping;
CREATE TABLE bronze.common_emp_node_role_mapping
ENGINE = MergeTree()
ORDER BY (EmpCode, NodeCode)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.EmpNodeRoleMapping');

-- 12. EmpOrgInfoMapping（員工-組織對應）
DROP TABLE IF EXISTS bronze.common_emp_org_info_mapping;
CREATE TABLE bronze.common_emp_org_info_mapping
ENGINE = MergeTree()
ORDER BY (EmpCode, OrgCode)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.EmpOrgInfoMapping');

-- 13. EmpUserGroupMapping（員工-群組對應）
DROP TABLE IF EXISTS bronze.common_emp_user_group_mapping;
CREATE TABLE bronze.common_emp_user_group_mapping
ENGINE = MergeTree()
ORDER BY (EmpCode, UserGroupId)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.EmpUserGroupMapping');

-- 14. UserGroup（使用者群組定義）
DROP TABLE IF EXISTS bronze.common_user_group;
CREATE TABLE bronze.common_user_group
ENGINE = MergeTree()
ORDER BY UserGroupId
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.UserGroup');

-- 15. DMPFunctionConfig（功能設定）
DROP TABLE IF EXISTS bronze.common_dmp_function_config;
CREATE TABLE bronze.common_dmp_function_config
ENGINE = MergeTree()
ORDER BY (FunctionCode, Plant)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.DMPFunctionConfig');

-- 16. DMPFunctionClientMapping（客戶端對應）
DROP TABLE IF EXISTS bronze.common_dmp_function_client_mapping;
CREATE TABLE bronze.common_dmp_function_client_mapping
ENGINE = MergeTree()
ORDER BY (Region, Plant)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.DMPFunctionClientMapping');

-- ============================================
-- 驗證：顯示所有表的 row count
-- ============================================
SELECT 'bpm_act_hi_procinst' as table_name, count(*) as row_count FROM bronze.bpm_act_hi_procinst
UNION ALL SELECT 'bpm_act_hi_taskinst', count(*) FROM bronze.bpm_act_hi_taskinst
UNION ALL SELECT 'bpm_act_hi_identitylink', count(*) FROM bronze.bpm_act_hi_identitylink
UNION ALL SELECT 'bpm_act_hi_varinst', count(*) FROM bronze.bpm_act_hi_varinst
UNION ALL SELECT 'bpm_act_re_procdef', count(*) FROM bronze.bpm_act_re_procdef
UNION ALL SELECT 'common_flowable_task_stats', count(*) FROM bronze.common_flowable_task_stats
UNION ALL SELECT 'common_hr_employee', count(*) FROM bronze.common_hr_employee
UNION ALL SELECT 'common_process_role_user_mapping', count(*) FROM bronze.common_process_role_user_mapping
UNION ALL SELECT 'common_process_role_group', count(*) FROM bronze.common_process_role_group
UNION ALL SELECT 'common_process_role_group_mapping', count(*) FROM bronze.common_process_role_group_mapping
UNION ALL SELECT 'common_emp_node_role_mapping', count(*) FROM bronze.common_emp_node_role_mapping
UNION ALL SELECT 'common_emp_org_info_mapping', count(*) FROM bronze.common_emp_org_info_mapping
UNION ALL SELECT 'common_emp_user_group_mapping', count(*) FROM bronze.common_emp_user_group_mapping
UNION ALL SELECT 'common_user_group', count(*) FROM bronze.common_user_group
UNION ALL SELECT 'common_dmp_function_config', count(*) FROM bronze.common_dmp_function_config
UNION ALL SELECT 'common_dmp_function_client_mapping', count(*) FROM bronze.common_dmp_function_client_mapping
ORDER BY table_name;
