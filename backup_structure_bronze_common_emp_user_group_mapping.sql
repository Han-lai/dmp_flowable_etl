-- 備份時間: 2026-01-20 10:49:46.243395
-- 原始表格: bronze.common_emp_user_group_mapping

CREATE TABLE bronze.common_emp_user_group_mapping
(
    `EmpCode` String,
    `UserGroupId` Int32,
    `UpdateTime` DateTime64(3),
    `UpdateEmp` String
)
ENGINE = MergeTree
ORDER BY tuple()
SETTINGS index_granularity = 8192;
