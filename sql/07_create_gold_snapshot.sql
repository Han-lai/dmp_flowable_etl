-- ============================================================
-- Gold Layer: Daily Metrics Snapshot
-- 每日指標快照表
-- 
-- 快照時間: 每日 10:00 Asia/Taipei (= 02:00 UTC)
-- 保留期限: 365 天
-- 維度: factory, plant, proc_def_name
-- ============================================================

-- 建立 gold schema
CREATE DATABASE IF NOT EXISTS gold;

-- ============================================================
-- 1. 任務層 + 流程層 每日快照表
-- ============================================================
DROP TABLE IF EXISTS gold.DAILY_METRICS_SNAPSHOT;

CREATE TABLE gold.DAILY_METRICS_SNAPSHOT (
    -- 快照時間
    snapshot_date Date COMMENT '快照日期 (Asia/Taipei)',
    snapshot_time DateTime64(3, 'Asia/Taipei') COMMENT '快照時間戳',
    
    -- 維度（存最細粒度）
    factory LowCardinality(String) COMMENT '工廠',
    plant LowCardinality(String) COMMENT '產品線',
    proc_def_name LowCardinality(String) COMMENT '流程類型',
    
    -- 在途任務指標
    in_progress_task_count UInt64 DEFAULT 0 COMMENT '在途任務數 (TODO + DOING)',
    todo_count UInt64 DEFAULT 0 COMMENT '待辦任務數',
    doing_count UInt64 DEFAULT 0 COMMENT '進行中任務數',
    
    -- 自動完成率（分子分母）
    done_auto_count UInt64 DEFAULT 0 COMMENT '自動完成數',
    done_total_count UInt64 DEFAULT 0 COMMENT '已完成總數 (DONE + DONE_AUTO)',
    
    -- 平均處理時長（分子分母）
    total_work_duration_sec UInt64 DEFAULT 0 COMMENT '處理時長總和 (秒)',
    done_count UInt64 DEFAULT 0 COMMENT '已完成任務數 (DONE)',
    
    -- 流程實例指標
    in_progress_proc_count UInt64 DEFAULT 0 COMMENT '在途流程數',
    completed_proc_count UInt64 DEFAULT 0 COMMENT '已完成流程數',
    
    -- 版本號（用於重跑去重）
    _version UInt64 DEFAULT toUnixTimestamp64Milli(now64(3, 'Asia/Taipei')) COMMENT '版本號'
    
) ENGINE = ReplacingMergeTree(_version)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (snapshot_date, factory, plant, proc_def_name)
TTL snapshot_date + INTERVAL 365 DAY DELETE
SETTINGS index_granularity = 8192
COMMENT 'Gold 層每日指標快照（任務+流程），保留 365 天';

-- ============================================================
-- 2. 業務事件層 每日快照表（獨立，因為沒有 factory/plant 維度）
-- ============================================================
DROP TABLE IF EXISTS gold.DAILY_BIZ_EVENT_SNAPSHOT;

CREATE TABLE gold.DAILY_BIZ_EVENT_SNAPSHOT (
    -- 快照時間
    snapshot_date Date COMMENT '快照日期 (Asia/Taipei)',
    snapshot_time DateTime64(3, 'Asia/Taipei') COMMENT '快照時間戳',
    
    -- 維度
    first_proc_def_name LowCardinality(String) COMMENT '首個流程類型',
    
    -- 業務事件指標
    in_progress_event_count UInt64 DEFAULT 0 COMMENT '在途業務事件數',
    completed_event_count UInt64 DEFAULT 0 COMMENT '已完成業務事件數',
    total_event_duration_sec UInt64 DEFAULT 0 COMMENT '業務事件總歷時 (秒)',
    
    -- 版本號（用於重跑去重）
    _version UInt64 DEFAULT toUnixTimestamp64Milli(now64(3, 'Asia/Taipei')) COMMENT '版本號'
    
) ENGINE = ReplacingMergeTree(_version)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (snapshot_date, first_proc_def_name)
TTL snapshot_date + INTERVAL 365 DAY DELETE
SETTINGS index_granularity = 8192
COMMENT 'Gold 層每日業務事件快照，保留 365 天';
