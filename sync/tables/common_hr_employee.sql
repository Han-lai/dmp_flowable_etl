-- 同步 HR_Employee（員工主檔）
-- 來源：APP_SRV_COMMON

DROP TABLE IF EXISTS bronze.common_hr_employee;

CREATE TABLE bronze.common_hr_employee
ENGINE = MergeTree()
ORDER BY EmpCode
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.HR_Employee');

SELECT 'common_hr_employee' as table_name, count(*) as row_count FROM bronze.common_hr_employee;
