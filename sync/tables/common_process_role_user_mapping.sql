-- 同步 ProcessRoleUserMapping（角色-員工對應）
-- 來源：APP_SRV_COMMON

DROP TABLE IF EXISTS bronze.common_process_role_user_mapping;

CREATE TABLE bronze.common_process_role_user_mapping
ENGINE = MergeTree()
ORDER BY (EmpCode, RoleCode)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping');

SELECT 'common_process_role_user_mapping' as table_name, count(*) as row_count FROM bronze.common_process_role_user_mapping;
