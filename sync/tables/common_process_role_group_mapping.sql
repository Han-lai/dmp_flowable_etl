-- 同步 ProcessRoleGroupMapping（角色群組對應）
-- 來源：APP_SRV_COMMON

DROP TABLE IF EXISTS bronze.common_process_role_group_mapping;

CREATE TABLE bronze.common_process_role_group_mapping
ENGINE = MergeTree()
ORDER BY (GroupCode, RoleCode)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.ProcessRoleGroupMapping');

SELECT 'common_process_role_group_mapping' as table_name, count(*) as row_count FROM bronze.common_process_role_group_mapping;
