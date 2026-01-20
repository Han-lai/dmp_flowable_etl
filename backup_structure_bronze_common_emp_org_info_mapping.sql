-- 備份時間: 2026-01-20 10:49:46.194824
-- 原始表格: bronze.common_emp_org_info_mapping

CREATE TABLE bronze.common_emp_org_info_mapping
(
    `EmpCode` String,
    `Plant` String,
    `MFGFactoryId` String,
    `UpdateTime` DateTime64(3),
    `UpdateEmp` String
)
ENGINE = MergeTree
ORDER BY tuple()
SETTINGS index_granularity = 8192;
