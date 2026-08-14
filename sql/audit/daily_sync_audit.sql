-- =====================================================================
-- 每日同步對帳：一次比對全部 19 張表（單一結果集）
--
-- 使用方式：
--   1. 全文取代 <帳號> 與 <密碼> 為 MSSQL 連線帳密
--   2. 整份貼進 ClickHouse 執行（前段建代理表，中段查詢，末段清理）
--   3. 實測耗時約 170 秒（batch 表窗口 2 天）
--
-- 注意事項見 docs/DMP_Flowable_同步對帳SQL手冊.md：
--   * 本環境密碼遮蔽規則尚未部署，帳密會明文寫入 query_log（無 TTL）
--   * 中文欄位別名必須加反引號，否則 ClickHouse tokenizer 會拒絕
--   * varinst / identitylink / mdm_line_desc / kpi_user_config_log 四張表
--     排序鍵在來源端非唯一，故來源端也用 uniqExact(排序鍵) 去重後才比對
--
-- 實測通過：2026-08-14
-- =====================================================================

DROP TABLE IF EXISTS audit_src_hr_employee;
CREATE TABLE audit_src_hr_employee
(
    EmpCode String
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'HR_Employee_0503');

DROP TABLE IF EXISTS audit_src_emp_node_role;
CREATE TABLE audit_src_emp_node_role
(
    EmpCode String,
    NodeCode String
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'EmpNodeRoleMapping_0503');

DROP TABLE IF EXISTS audit_src_emp_org_info;
CREATE TABLE audit_src_emp_org_info
(
    EmpCode String,
    Plant String,
    MFGFactoryId String
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'EmpOrgInfoMapping_0503');

DROP TABLE IF EXISTS audit_src_emp_user_group;
CREATE TABLE audit_src_emp_user_group
(
    EmpCode String,
    UserGroupId Int32
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'EmpUserGroupMapping_0503');

DROP TABLE IF EXISTS audit_src_user_group;
CREATE TABLE audit_src_user_group
(
    UserGroupId Int32
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'UserGroup_0503');

DROP TABLE IF EXISTS audit_src_process_role_user;
CREATE TABLE audit_src_process_role_user
(
    ID Int32
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'ProcessRoleUserMapping_0503');

DROP TABLE IF EXISTS audit_src_mdm_line_desc;
CREATE TABLE audit_src_mdm_line_desc
(
    LINE_NAME String,
    PROD_AREA_ID String
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'MDM_LINE_DESC_MASTER_0503');

DROP TABLE IF EXISTS audit_src_mdm_prod_area;
CREATE TABLE audit_src_mdm_prod_area
(
    PROD_AREA_ID String
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'MDM_PROD_AREA_MASTER_0503');

DROP TABLE IF EXISTS audit_src_mdm_factory_area;
CREATE TABLE audit_src_mdm_factory_area
(
    FACTORY String
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'MDM_FACTORY_AREA_MASTER_0503');

DROP TABLE IF EXISTS audit_src_mdm_mfg_site;
CREATE TABLE audit_src_mdm_mfg_site
(
    MFG_SITE String
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'MDM_MFG_SITE_MASTER_0503');

DROP TABLE IF EXISTS audit_src_mdm_mfg_plant;
CREATE TABLE audit_src_mdm_mfg_plant
(
    MFG_PLANT_ID String
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'MDM_MFG_PLANT_MASTER_0503');

DROP TABLE IF EXISTS audit_src_dmp_func_config;
CREATE TABLE audit_src_dmp_func_config
(
    ID Int64
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'DMPFunctionConfig_0503');

DROP TABLE IF EXISTS audit_src_dmp_func_client_mapping;
CREATE TABLE audit_src_dmp_func_client_mapping
(
    ID Int64
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'DMPFunctionClientMapping_0503');

DROP TABLE IF EXISTS audit_src_procdef;
CREATE TABLE audit_src_procdef
(
    ID_ String
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_BPM;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'ACT_RE_PROCDEF_0503');

DROP TABLE IF EXISTS audit_src_taskinst;
CREATE TABLE audit_src_taskinst
(
    ID_ String,
    PROC_INST_ID_ String,
    LAST_UPDATED_TIME_ DateTime
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_BPM;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'ACT_HI_TASKINST_0503');

DROP TABLE IF EXISTS audit_src_varinst;
CREATE TABLE audit_src_varinst
(
    PROC_INST_ID_ String,
    NAME_ String,
    CREATE_TIME_ DateTime
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_BPM;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'ACT_HI_VARINST_0503');

DROP TABLE IF EXISTS audit_src_procinst;
CREATE TABLE audit_src_procinst
(
    PROC_INST_ID_ String,
    START_TIME_ DateTime
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_BPM;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'ACT_HI_PROCINST_0503');

DROP TABLE IF EXISTS audit_src_identitylink;
CREATE TABLE audit_src_identitylink
(
    USER_ID_ String,
    TYPE_ String,
    TASK_ID_ String,
    CREATE_TIME_ DateTime
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_BPM;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'ACT_HI_IDENTITYLINK_0503');

DROP TABLE IF EXISTS audit_src_kpi_user_config_log;
CREATE TABLE audit_src_kpi_user_config_log
(
    empCode String,
    Vx String,
    Plant String
)
ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_COMMON;Uid=<帳號>;Pwd=<密碼>;MARS_Connection=no', 'dbo', 'RptCommonKpiUserConfigLog_0503');

SELECT `分類`, `來源表`, `來源端筆數`, `目的表`, `目的端筆數`,
       `來源端筆數` - `目的端筆數` AS `未同步筆數`,
       round(`目的端筆數` * 100.0 / nullIf(`來源端筆數`, 0), 4) AS `同步百分比`
FROM (
    SELECT 1 AS ord, '人員/組織' AS `分類`, 'APP_SRV_COMMON.dbo.HR_Employee_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_hr_employee )) AS `來源端筆數`,
           'bronze.common_hr_employee' AS `目的表`,
           toInt64((SELECT uniqExact(EmpCode) FROM bronze.common_hr_employee )) AS `目的端筆數`
    UNION ALL
    SELECT 2 AS ord, '人員/組織' AS `分類`, 'APP_SRV_COMMON.dbo.EmpNodeRoleMapping_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_emp_node_role )) AS `來源端筆數`,
           'bronze.common_emp_node_role_mapping' AS `目的表`,
           toInt64((SELECT uniqExact(EmpCode, NodeCode) FROM bronze.common_emp_node_role_mapping )) AS `目的端筆數`
    UNION ALL
    SELECT 3 AS ord, '人員/組織' AS `分類`, 'APP_SRV_COMMON.dbo.EmpOrgInfoMapping_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_emp_org_info )) AS `來源端筆數`,
           'bronze.common_emp_org_info_mapping' AS `目的表`,
           toInt64((SELECT uniqExact(EmpCode, Plant, MFGFactoryId) FROM bronze.common_emp_org_info_mapping )) AS `目的端筆數`
    UNION ALL
    SELECT 4 AS ord, '人員/組織' AS `分類`, 'APP_SRV_COMMON.dbo.EmpUserGroupMapping_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_emp_user_group )) AS `來源端筆數`,
           'bronze.common_emp_user_group_mapping' AS `目的表`,
           toInt64((SELECT uniqExact(EmpCode, UserGroupId) FROM bronze.common_emp_user_group_mapping )) AS `目的端筆數`
    UNION ALL
    SELECT 5 AS ord, '人員/組織' AS `分類`, 'APP_SRV_COMMON.dbo.UserGroup_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_user_group )) AS `來源端筆數`,
           'bronze.common_user_group' AS `目的表`,
           toInt64((SELECT uniqExact(UserGroupId) FROM bronze.common_user_group )) AS `目的端筆數`
    UNION ALL
    SELECT 6 AS ord, '人員/組織' AS `分類`, 'APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_process_role_user )) AS `來源端筆數`,
           'bronze.common_process_role_user_mapping' AS `目的表`,
           toInt64((SELECT uniqExact(ID) FROM bronze.common_process_role_user_mapping )) AS `目的端筆數`
    UNION ALL
    SELECT 7 AS ord, '主檔(MDM)' AS `分類`, 'APP_SRV_COMMON.dbo.MDM_LINE_DESC_MASTER_0503' AS `來源表`,
           toInt64((SELECT uniqExact(PROD_AREA_ID, LINE_NAME) FROM audit_src_mdm_line_desc )) AS `來源端筆數`,
           'bronze.common_mdm_line_desc_master' AS `目的表`,
           toInt64((SELECT uniqExact(PROD_AREA_ID, LINE_NAME) FROM bronze.common_mdm_line_desc_master )) AS `目的端筆數`
    UNION ALL
    SELECT 8 AS ord, '主檔(MDM)' AS `分類`, 'APP_SRV_COMMON.dbo.MDM_PROD_AREA_MASTER_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_mdm_prod_area )) AS `來源端筆數`,
           'bronze.common_mdm_prod_area_master' AS `目的表`,
           toInt64((SELECT uniqExact(PROD_AREA_ID) FROM bronze.common_mdm_prod_area_master )) AS `目的端筆數`
    UNION ALL
    SELECT 9 AS ord, '主檔(MDM)' AS `分類`, 'APP_SRV_COMMON.dbo.MDM_FACTORY_AREA_MASTER_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_mdm_factory_area )) AS `來源端筆數`,
           'bronze.common_mdm_factory_area_master' AS `目的表`,
           toInt64((SELECT uniqExact(FACTORY) FROM bronze.common_mdm_factory_area_master )) AS `目的端筆數`
    UNION ALL
    SELECT 10 AS ord, '主檔(MDM)' AS `分類`, 'APP_SRV_COMMON.dbo.MDM_MFG_SITE_MASTER_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_mdm_mfg_site )) AS `來源端筆數`,
           'bronze.common_mdm_mfg_site_master' AS `目的表`,
           toInt64((SELECT uniqExact(MFG_SITE) FROM bronze.common_mdm_mfg_site_master )) AS `目的端筆數`
    UNION ALL
    SELECT 11 AS ord, '主檔(MDM)' AS `分類`, 'APP_SRV_COMMON.dbo.MDM_MFG_PLANT_MASTER_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_mdm_mfg_plant )) AS `來源端筆數`,
           'bronze.common_mdm_mfg_plant_master' AS `目的表`,
           toInt64((SELECT uniqExact(MFG_PLANT_ID) FROM bronze.common_mdm_mfg_plant_master )) AS `目的端筆數`
    UNION ALL
    SELECT 12 AS ord, '功能設定' AS `分類`, 'APP_SRV_COMMON.dbo.DMPFunctionConfig_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_dmp_func_config )) AS `來源端筆數`,
           'bronze.common_dmp_function_config' AS `目的表`,
           toInt64((SELECT uniqExact(ID) FROM bronze.common_dmp_function_config )) AS `目的端筆數`
    UNION ALL
    SELECT 13 AS ord, '功能設定' AS `分類`, 'APP_SRV_COMMON.dbo.DMPFunctionClientMapping_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_dmp_func_client_mapping )) AS `來源端筆數`,
           'bronze.common_dmp_function_client_mapping' AS `目的表`,
           toInt64((SELECT uniqExact(ID) FROM bronze.common_dmp_function_client_mapping )) AS `目的端筆數`
    UNION ALL
    SELECT 14 AS ord, '流程引擎(BPM)' AS `分類`, 'APP_SRV_BPM.dbo.ACT_RE_PROCDEF_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_procdef )) AS `來源端筆數`,
           'bronze.bpm_act_re_procdef' AS `目的表`,
           toInt64((SELECT uniqExact(ID_) FROM bronze.bpm_act_re_procdef )) AS `目的端筆數`
    UNION ALL
    SELECT 15 AS ord, '流程引擎(BPM)' AS `分類`, 'APP_SRV_BPM.dbo.ACT_HI_TASKINST_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_taskinst WHERE LAST_UPDATED_TIME_ >= greatest((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_taskinst') - INTERVAL 2 DAY, toDateTime('2025-10-01 00:00:00')) AND LAST_UPDATED_TIME_ < (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_taskinst'))) AS `來源端筆數`,
           'bronze.bpm_act_hi_taskinst' AS `目的表`,
           toInt64((SELECT uniqExact(PROC_INST_ID_, ID_) FROM bronze.bpm_act_hi_taskinst WHERE LAST_UPDATED_TIME_ >= greatest((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_taskinst') - INTERVAL 2 DAY, toDateTime('2025-10-01 00:00:00')) AND LAST_UPDATED_TIME_ < (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_taskinst'))) AS `目的端筆數`
    UNION ALL
    SELECT 16 AS ord, '流程引擎(BPM)' AS `分類`, 'APP_SRV_BPM.dbo.ACT_HI_VARINST_0503' AS `來源表`,
           toInt64((SELECT uniqExact(PROC_INST_ID_, NAME_, CREATE_TIME_) FROM audit_src_varinst WHERE CREATE_TIME_ >= greatest((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_varinst') - INTERVAL 2 DAY, toDateTime('2025-10-01 00:00:00')) AND CREATE_TIME_ < (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_varinst'))) AS `來源端筆數`,
           'bronze.bpm_act_hi_varinst' AS `目的表`,
           toInt64((SELECT uniqExact(PROC_INST_ID_, NAME_, CREATE_TIME_) FROM bronze.bpm_act_hi_varinst WHERE CREATE_TIME_ >= greatest((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_varinst') - INTERVAL 2 DAY, toDateTime('2025-10-01 00:00:00')) AND CREATE_TIME_ < (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_varinst'))) AS `目的端筆數`
    UNION ALL
    SELECT 17 AS ord, '流程引擎(BPM)' AS `分類`, 'APP_SRV_BPM.dbo.ACT_HI_PROCINST_0503' AS `來源表`,
           toInt64((SELECT count() FROM audit_src_procinst WHERE START_TIME_ >= greatest((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_procinst') - INTERVAL 2 DAY, toDateTime('2025-10-01 00:00:00')) AND START_TIME_ < (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_procinst'))) AS `來源端筆數`,
           'bronze.bpm_act_hi_procinst' AS `目的表`,
           toInt64((SELECT uniqExact(PROC_INST_ID_) FROM bronze.bpm_act_hi_procinst WHERE START_TIME_ >= greatest((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_procinst') - INTERVAL 2 DAY, toDateTime('2025-10-01 00:00:00')) AND START_TIME_ < (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_procinst'))) AS `目的端筆數`
    UNION ALL
    SELECT 18 AS ord, '流程引擎(BPM)' AS `分類`, 'APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0503' AS `來源表`,
           toInt64((SELECT uniqExact(TASK_ID_, USER_ID_, TYPE_) FROM audit_src_identitylink WHERE CREATE_TIME_ >= greatest((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_identitylink') - INTERVAL 2 DAY, toDateTime('2025-10-01 00:00:00')) AND CREATE_TIME_ < (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_identitylink'))) AS `來源端筆數`,
           'bronze.bpm_act_hi_identitylink' AS `目的表`,
           toInt64((SELECT uniqExact(TASK_ID_, USER_ID_, TYPE_) FROM bronze.bpm_act_hi_identitylink WHERE CREATE_TIME_ >= greatest((SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_identitylink') - INTERVAL 2 DAY, toDateTime('2025-10-01 00:00:00')) AND CREATE_TIME_ < (SELECT toDateTime(max(max_data_time)) FROM bronze._sync_watermark FINAL WHERE table_name = 'bronze.bpm_act_hi_identitylink'))) AS `目的端筆數`
    UNION ALL
    SELECT 19 AS ord, '人員每日匯總' AS `分類`, 'APP_SRV_COMMON.dbo.RptCommonKpiUserConfigLog_0503' AS `來源表`,
           toInt64((SELECT uniqExact(empCode, Vx, Plant) FROM audit_src_kpi_user_config_log )) AS `來源端筆數`,
           'bronze.common_rptkpiuserconfiglog' AS `目的表`,
           toInt64((SELECT uniqExact(empCode, Vx, Plant) FROM bronze.common_rptkpiuserconfiglog )) AS `目的端筆數`
)
ORDER BY ord
SETTINGS max_execution_time = 3600;


-- ===== 清理代理表（表定義含密碼，用完務必刪除）=====
DROP TABLE IF EXISTS audit_src_hr_employee;
DROP TABLE IF EXISTS audit_src_emp_node_role;
DROP TABLE IF EXISTS audit_src_emp_org_info;
DROP TABLE IF EXISTS audit_src_emp_user_group;
DROP TABLE IF EXISTS audit_src_user_group;
DROP TABLE IF EXISTS audit_src_process_role_user;
DROP TABLE IF EXISTS audit_src_mdm_line_desc;
DROP TABLE IF EXISTS audit_src_mdm_prod_area;
DROP TABLE IF EXISTS audit_src_mdm_factory_area;
DROP TABLE IF EXISTS audit_src_mdm_mfg_site;
DROP TABLE IF EXISTS audit_src_mdm_mfg_plant;
DROP TABLE IF EXISTS audit_src_dmp_func_config;
DROP TABLE IF EXISTS audit_src_dmp_func_client_mapping;
DROP TABLE IF EXISTS audit_src_procdef;
DROP TABLE IF EXISTS audit_src_taskinst;
DROP TABLE IF EXISTS audit_src_varinst;
DROP TABLE IF EXISTS audit_src_procinst;
DROP TABLE IF EXISTS audit_src_identitylink;
DROP TABLE IF EXISTS audit_src_kpi_user_config_log;
