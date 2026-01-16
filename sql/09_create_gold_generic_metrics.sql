-- ============================================
-- Gold 層 - 通用指標快照表
-- 支撐指標：L5 任務執行完成率、人員使用率
-- 建立日期：2026-01-15
-- ============================================

-- ============================================
-- 表 1: DAILY_L5_TASK_COMPLETION_SNAPSHOT
-- 用途：L5 任務執行完成率每日快照
-- ============================================

DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT;

CREATE TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
(
    -- 快照日期
    snapshot_date Date,
    
    -- 維度 (ORDER BY 欄位不可為 Nullable)
    vx_type LowCardinality(String),              -- V1/V2/V3
    vx_subtype String DEFAULT '',                -- V1_NPE/V1_MFG/空字串
    plant String DEFAULT '',
    factory String DEFAULT '',
    line String DEFAULT '',
    
    -- 時間區間類型
    time_period_type LowCardinality(String),     -- total/month/week/day
    time_period_value String,                    -- 2026-01 / W03 / 2026-01-15
    
    -- 指標：任務數
    total_task_qty UInt32,
    todo_qty UInt32,
    doing_qty UInt32,
    done_qty UInt32,
    doing_done_qty UInt32,
    todo_doing_acc_qty UInt32,
    
    -- 指標：百分比（預計算）
    todo_pct Decimal(5, 2),
    doing_pct Decimal(5, 2),
    done_pct Decimal(5, 2),
    doing_done_pct Decimal(5, 2),
    
    -- Metadata
    _version UInt64 DEFAULT toUnixTimestamp64Milli(now64(3)),
    _snapshot_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_version)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (snapshot_date, vx_type, vx_subtype, plant, factory, line, time_period_type, time_period_value)
TTL snapshot_date + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;

-- ============================================
-- 表 2: DAILY_USER_UTILIZATION_SNAPSHOT
-- 用途：人員使用率每日快照
-- ============================================

DROP TABLE IF EXISTS gold.DAILY_USER_UTILIZATION_SNAPSHOT;

CREATE TABLE gold.DAILY_USER_UTILIZATION_SNAPSHOT
(
    -- 快照日期
    snapshot_date Date,
    
    -- 維度 (ORDER BY 欄位不可為 Nullable)
    vx_type LowCardinality(String),              -- V1/V2/V3
    plant String DEFAULT '',
    factory String DEFAULT '',
    line String DEFAULT '',
    
    -- 時間區間類型
    time_period_type LowCardinality(String),     -- total/month/week/day
    time_period_value String,                    -- 2026-01 / W03 / 2026-01-15
    
    -- 指標：人數
    active_users UInt32,
    config_users UInt32,
    
    -- 指標：使用率（預計算）
    utilization_rate Decimal(5, 2),
    
    -- Metadata
    _version UInt64 DEFAULT toUnixTimestamp64Milli(now64(3)),
    _snapshot_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_version)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (snapshot_date, vx_type, plant, factory, time_period_type, time_period_value)
TTL snapshot_date + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;
