-- 同步 EmpNodeRoleMapping（員工-節點角色）
-- 來源：APP_SRV_COMMON

DROP TABLE IF EXISTS bronze.common_emp_node_role_mapping;

CREATE TABLE bronze.common_emp_node_role_mapping
ENGINE = MergeTree()
ORDER BY (EmpCode, NodeCode)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.EmpNodeRoleMapping');

SELECT 'common_emp_node_role_mapping' as table_name, count(*) as row_count FROM bronze.common_emp_node_role_mapping;
