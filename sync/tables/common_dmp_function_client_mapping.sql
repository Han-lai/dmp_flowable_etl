-- 同步 DMPFunctionClientMapping（客戶端對應）
-- 來源：APP_SRV_COMMON

DROP TABLE IF EXISTS bronze.common_dmp_function_client_mapping;

CREATE TABLE bronze.common_dmp_function_client_mapping
ENGINE = MergeTree()
ORDER BY (Region, Plant)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.DMPFunctionClientMapping');

SELECT 'common_dmp_function_client_mapping' as table_name, count(*) as row_count FROM bronze.common_dmp_function_client_mapping;
