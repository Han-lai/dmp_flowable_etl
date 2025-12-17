-- ============================================
-- 測試：同步單張表 (HR_Employee)
-- 使用 CREATE TABLE AS SELECT 一步完成建表+同步
-- ============================================

-- 1. 確認 bronze database 存在
CREATE DATABASE IF NOT EXISTS bronze;

-- 2. 如果表已存在，先刪除
DROP TABLE IF EXISTS bronze.common_hr_employee;

-- 3. 建表 + 同步（一步完成）
CREATE TABLE bronze.common_hr_employee
ENGINE = MergeTree()
ORDER BY EmpCode
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.HR_Employee');

-- 4. 確認資料筆數
SELECT 
    'bronze.common_hr_employee' as table_name,
    count(*) as row_count
FROM bronze.common_hr_employee;

-- 5. 查看前 5 筆資料
SELECT * FROM bronze.common_hr_employee LIMIT 5;
