-- 同步 UserGroup（使用者群組定義）
-- 來源：APP_SRV_COMMON

DROP TABLE IF EXISTS bronze.common_user_group;

CREATE TABLE bronze.common_user_group
ENGINE = MergeTree()
ORDER BY UserGroupId
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.UserGroup');

SELECT 'common_user_group' as table_name, count(*) as row_count FROM bronze.common_user_group;
