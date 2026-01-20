-- 備份時間: 2026-01-20 10:49:46.136338
-- 原始表格: bronze.common_emp_node_role_mapping

CREATE TABLE bronze.common_emp_node_role_mapping
(
    `EmpCode` String,
    `NodeCode` String,
    `UpdateTime` DateTime64(3),
    `UpdateEmp` String,
    `Vx` String
)
ENGINE = MergeTree
ORDER BY tuple()
SETTINGS index_granularity = 8192;
