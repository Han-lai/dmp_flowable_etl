-- 同步 EmpUserGroupMapping（員工-群組對應）
-- 來源：APP_SRV_COMMON

DROP TABLE IF EXISTS bronze.common_emp_user_group_mapping;

CREATE TABLE bronze.common_emp_user_group_mapping
ENGINE = MergeTree()
ORDER BY (EmpCode, UserGroupId)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.EmpUserGroupMapping');

SELECT 'common_emp_user_group_mapping' as table_name, count(*) as row_count FROM bronze.common_emp_user_group_mapping;
