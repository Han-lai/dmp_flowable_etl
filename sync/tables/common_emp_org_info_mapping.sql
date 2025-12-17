-- 同步 EmpOrgInfoMapping（員工-組織對應）
-- 來源：APP_SRV_COMMON

DROP TABLE IF EXISTS bronze.common_emp_org_info_mapping;

CREATE TABLE bronze.common_emp_org_info_mapping
ENGINE = MergeTree()
ORDER BY (EmpCode, OrgCode)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.EmpOrgInfoMapping');

SELECT 'common_emp_org_info_mapping' as table_name, count(*) as row_count FROM bronze.common_emp_org_info_mapping;
