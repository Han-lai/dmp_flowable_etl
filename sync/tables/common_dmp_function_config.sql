-- 同步 DMPFunctionConfig（功能設定）
-- 來源：APP_SRV_COMMON

DROP TABLE IF EXISTS bronze.common_dmp_function_config;

CREATE TABLE bronze.common_dmp_function_config
ENGINE = MergeTree()
ORDER BY (FunctionCode, Plant)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.DMPFunctionConfig');

SELECT 'common_dmp_function_config' as table_name, count(*) as row_count FROM bronze.common_dmp_function_config;
