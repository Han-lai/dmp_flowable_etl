-- ============================================
-- Bronze Database 建立腳本
-- ============================================

-- 建立 Bronze Database
CREATE DATABASE IF NOT EXISTS bronze;

-- 建立同步狀態追蹤表
CREATE TABLE IF NOT EXISTS bronze._sync_log
(
    batch_id String,
    source_db LowCardinality(String),
    table_name LowCardinality(String),
    sync_type Enum8('full' = 1, 'incremental' = 2),
    start_time DateTime64(3),
    end_time Nullable(DateTime64(3)),
    status Enum8('running' = 1, 'success' = 2, 'failed' = 3),
    rows_read UInt64 DEFAULT 0,
    rows_written UInt64 DEFAULT 0,
    error_message Nullable(String),
    last_sync_value Nullable(String)  -- 增量同步的最後時間戳
)
ENGINE = MergeTree()
ORDER BY (source_db, table_name, start_time)
SETTINGS index_granularity = 8192;

-- 建立同步設定表（記錄每張表的同步策略）
CREATE TABLE IF NOT EXISTS bronze._sync_config
(
    source_db LowCardinality(String),
    table_name LowCardinality(String),
    sync_type Enum8('full' = 1, 'incremental' = 2),
    time_column Nullable(String),           -- 增量同步使用的時間欄位
    sync_interval_minutes UInt32 DEFAULT 60, -- 同步間隔（分鐘）
    is_enabled UInt8 DEFAULT 1,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (source_db, table_name)
SETTINGS index_granularity = 8192;

-- 插入同步設定
INSERT INTO bronze._sync_config (source_db, table_name, sync_type, time_column, sync_interval_minutes) VALUES
-- APP_SRV_BPM (Flowable)
('APP_SRV_BPM', 'ACT_HI_PROCINST', 'incremental', 'START_TIME_', 60),
('APP_SRV_BPM', 'ACT_HI_TASKINST', 'incremental', 'LAST_UPDATED_TIME_', 60),
('APP_SRV_BPM', 'ACT_HI_IDENTITYLINK', 'incremental', 'CREATE_TIME_', 60),
('APP_SRV_BPM', 'ACT_HI_VARINST', 'incremental', 'LAST_UPDATED_TIME_', 60),
('APP_SRV_BPM', 'ACT_RE_PROCDEF', 'full', NULL, 1440),  -- 每日全量

-- APP_SRV_COMMON (DMP)
('APP_SRV_COMMON', 'FlowableTaskStats', 'incremental', 'LastUpdatedTime', 15),
('APP_SRV_COMMON', 'HR_Employee', 'full', 'ModifyDate', 1440),  -- 每日全量
('APP_SRV_COMMON', 'ProcessRoleUserMapping', 'incremental', 'UpdateDatetime', 60),
('APP_SRV_COMMON', 'ProcessRoleGroup', 'full', NULL, 1440),
('APP_SRV_COMMON', 'ProcessRoleGroupMapping', 'incremental', 'UpdateDatetime', 60),
('APP_SRV_COMMON', 'EmpNodeRoleMapping', 'incremental', 'UpdateTime', 60),
('APP_SRV_COMMON', 'EmpOrgInfoMapping', 'incremental', 'UpdateTime', 60),
('APP_SRV_COMMON', 'EmpUserGroupMapping', 'incremental', 'UpdateTime', 60),
('APP_SRV_COMMON', 'UserGroup', 'full', NULL, 1440),
('APP_SRV_COMMON', 'DMPFunctionConfig', 'full', NULL, 1440),
('APP_SRV_COMMON', 'DMPFunctionClientMapping', 'full', NULL, 1440);
