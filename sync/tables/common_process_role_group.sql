-- 同步 ProcessRoleGroup（角色群組定義）
-- 來源：APP_SRV_COMMON

DROP TABLE IF EXISTS bronze.common_process_role_group;

CREATE TABLE bronze.common_process_role_group
ENGINE = MergeTree()
ORDER BY GroupCode
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.ProcessRoleGroup');

SELECT 'common_process_role_group' as table_name, count(*) as row_count FROM bronze.common_process_role_group;
