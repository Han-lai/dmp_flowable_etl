-- ============================================
-- Row Count 比對查詢
-- 比對 MSSQL 與 ClickHouse 的資料筆數
-- ============================================

-- APP_SRV_BPM 表 Row Count 比對
SELECT 
    'bpm_act_hi_procinst' as table_name,
    (SELECT count(*) FROM bronze.bpm_act_hi_procinst) as clickhouse_count,
    (SELECT count(*) FROM jdbc('mssql_bpm', 'SELECT COUNT(*) as cnt FROM ACT_HI_PROCINST')) as mssql_count,
    (SELECT count(*) FROM bronze.bpm_act_hi_procinst) - 
    (SELECT count(*) FROM jdbc('mssql_bpm', 'SELECT COUNT(*) as cnt FROM ACT_HI_PROCINST')) as diff

UNION ALL

SELECT 
    'bpm_act_hi_taskinst',
    (SELECT count(*) FROM bronze.bpm_act_hi_taskinst),
    (SELECT count(*) FROM jdbc('mssql_bpm', 'SELECT COUNT(*) as cnt FROM ACT_HI_TASKINST')),
    (SELECT count(*) FROM bronze.bpm_act_hi_taskinst) - 
    (SELECT count(*) FROM jdbc('mssql_bpm', 'SELECT COUNT(*) as cnt FROM ACT_HI_TASKINST'))

UNION ALL

SELECT 
    'bpm_act_hi_identitylink',
    (SELECT count(*) FROM bronze.bpm_act_hi_identitylink),
    (SELECT count(*) FROM jdbc('mssql_bpm', 'SELECT COUNT(*) as cnt FROM ACT_HI_IDENTITYLINK')),
    (SELECT count(*) FROM bronze.bpm_act_hi_identitylink) - 
    (SELECT count(*) FROM jdbc('mssql_bpm', 'SELECT COUNT(*) as cnt FROM ACT_HI_IDENTITYLINK'))

UNION ALL

SELECT 
    'bpm_act_hi_varinst',
    (SELECT count(*) FROM bronze.bpm_act_hi_varinst),
    (SELECT count(*) FROM jdbc('mssql_bpm', 'SELECT COUNT(*) as cnt FROM ACT_HI_VARINST')),
    (SELECT count(*) FROM bronze.bpm_act_hi_varinst) - 
    (SELECT count(*) FROM jdbc('mssql_bpm', 'SELECT COUNT(*) as cnt FROM ACT_HI_VARINST'))

UNION ALL

SELECT 
    'bpm_act_re_procdef',
    (SELECT count(*) FROM bronze.bpm_act_re_procdef),
    (SELECT count(*) FROM jdbc('mssql_bpm', 'SELECT COUNT(*) as cnt FROM ACT_RE_PROCDEF')),
    (SELECT count(*) FROM bronze.bpm_act_re_procdef) - 
    (SELECT count(*) FROM jdbc('mssql_bpm', 'SELECT COUNT(*) as cnt FROM ACT_RE_PROCDEF'));


-- APP_SRV_COMMON 表 Row Count 比對
SELECT 
    'common_flowable_task_stats' as table_name,
    (SELECT count(*) FROM bronze.common_flowable_task_stats) as clickhouse_count,
    (SELECT count(*) FROM jdbc('mssql_common', 'SELECT COUNT(*) as cnt FROM FlowableTaskStats')) as mssql_count,
    (SELECT count(*) FROM bronze.common_flowable_task_stats) - 
    (SELECT count(*) FROM jdbc('mssql_common', 'SELECT COUNT(*) as cnt FROM FlowableTaskStats')) as diff

UNION ALL

SELECT 
    'common_hr_employee',
    (SELECT count(*) FROM bronze.common_hr_employee),
    (SELECT count(*) FROM jdbc('mssql_common', 'SELECT COUNT(*) as cnt FROM HR_Employee')),
    (SELECT count(*) FROM bronze.common_hr_employee) - 
    (SELECT count(*) FROM jdbc('mssql_common', 'SELECT COUNT(*) as cnt FROM HR_Employee'))

UNION ALL

SELECT 
    'common_process_role_user_mapping',
    (SELECT count(*) FROM bronze.common_process_role_user_mapping),
    (SELECT count(*) FROM jdbc('mssql_common', 'SELECT COUNT(*) as cnt FROM ProcessRoleUserMapping')),
    (SELECT count(*) FROM bronze.common_process_role_user_mapping) - 
    (SELECT count(*) FROM jdbc('mssql_common', 'SELECT COUNT(*) as cnt FROM ProcessRoleUserMapping'))

UNION ALL

SELECT 
    'common_process_role_group',
    (SELECT count(*) FROM bronze.common_process_role_group),
    (SELECT count(*) FROM jdbc('mssql_common', 'SELECT COUNT(*) as cnt FROM ProcessRoleGroup')),
    (SELECT count(*) FROM bronze.common_process_role_group) - 
    (SELECT count(*) FROM jdbc('mssql_common', 'SELECT COUNT(*) as cnt FROM ProcessRoleGroup'))

UNION ALL

SELECT 
    'common_user_group',
    (SELECT count(*) FROM bronze.common_user_group),
    (SELECT count(*) FROM jdbc('mssql_common', 'SELECT COUNT(*) as cnt FROM UserGroup')),
    (SELECT count(*) FROM bronze.common_user_group) - 
    (SELECT count(*) FROM jdbc('mssql_common', 'SELECT COUNT(*) as cnt FROM UserGroup'));
