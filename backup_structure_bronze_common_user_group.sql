-- 備份時間: 2026-01-20 10:49:46.738198
-- 原始表格: bronze.common_user_group

CREATE TABLE bronze.common_user_group
(
    `UserGroupId` Int32,
    `UserGroupName` String,
    `UserGroupDesc` String,
    `UpdateTime` DateTime64(3),
    `UpdateEmp` String
)
ENGINE = MergeTree
ORDER BY tuple()
SETTINGS index_granularity = 8192;
