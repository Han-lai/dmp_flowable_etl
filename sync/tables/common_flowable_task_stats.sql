-- 同步 FlowableTaskStats（任務統計彙總）
-- 來源：APP_SRV_COMMON

DROP TABLE IF EXISTS bronze.common_flowable_task_stats;

CREATE TABLE bronze.common_flowable_task_stats
ENGINE = MergeTree()
ORDER BY (TaskId, Id)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.FlowableTaskStats');

SELECT 'common_flowable_task_stats' as table_name, count(*) as row_count FROM bronze.common_flowable_task_stats;
