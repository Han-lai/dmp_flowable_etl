-- ============================================
-- Silver 層 - 通用指標資料模型
-- 支撐指標：L5 任務執行完成率、人員使用率
-- 建立日期：2026-01-15
-- ============================================

-- ============================================
-- 表 1: FACT_TASK_VX_ATTRIBUTION
-- 用途：任務 Vx 歸屬事實表
-- 支撐：L5 任務執行完成率 + Active Users
-- ============================================

DROP TABLE IF EXISTS silver.FACT_TASK_VX_ATTRIBUTION;

CREATE TABLE silver.FACT_TASK_VX_ATTRIBUTION
(
    -- 主鍵
    task_id String,
    
    -- 時間維度
    task_create_date Date,
    task_end_date Nullable(Date),
    task_create_time Nullable(DateTime64(3)),    -- 用於計算「當天狀態」
    task_claim_time Nullable(DateTime64(3)),     -- 用於計算「當天狀態」
    task_end_time Nullable(DateTime64(3)),       -- 用於計算「當天狀態」
    
    -- 任務屬性
    task_status LowCardinality(String),          -- TODO/DOING/DONE
    task_bypass LowCardinality(String),          -- Y/N
    task_definition_key Nullable(String),
    task_name Nullable(String),
    
    -- 人員資訊（供 Active Users 使用）
    task_assignee_name Nullable(String),
    task_assignee_account Nullable(String),
    
    -- 預計算：Vx 歸屬
    vx_type LowCardinality(String),              -- V1/V2/V3/...
    vx_subtype LowCardinality(Nullable(String)), -- V1_NPE/V1_MFG/NULL
    is_special_v1_rule UInt8,                    -- 是否套用特殊 V1 規則（MoNumber 196/199/200/210/212/213/315）
    
    -- 排除標記
    is_excluded UInt8,                           -- 是否被排除
    exclude_reason Nullable(String),             -- 排除原因
    
    -- 維度 (ORDER BY 欄位不可為 Nullable)
    plant String DEFAULT '',
    factory Nullable(String),
    line Nullable(String),
    
    -- 關聯欄位
    proc_inst_id Nullable(String),
    business_key Nullable(String),
    mo_number Nullable(String),
    proc_name Nullable(String),                  -- 用於 Q/R 工單判斷
    
    -- Metadata
    _transform_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_transform_time)
PARTITION BY toYYYYMM(task_create_date)
ORDER BY (vx_type, plant, task_create_date, task_id)
SETTINGS index_granularity = 8192;

-- ============================================
-- 表 2: DIM_CONFIG_USER
-- 用途：Config Users 維度表
-- 支撐：人員使用率
-- ============================================

DROP TABLE IF EXISTS silver.DIM_CONFIG_USER;

CREATE TABLE silver.DIM_CONFIG_USER
(
    -- 主鍵 (ORDER BY 欄位不可為 Nullable)
    emp_code String,
    vx_type LowCardinality(String),              -- V1/V2/V3
    plant String DEFAULT '',
    factory String DEFAULT '',
    
    -- 員工資訊
    emp_name Nullable(String),
    
    -- 預計算：成員資格
    is_config_user UInt8,                        -- 是否為 Config User
    is_excluded UInt8,                           -- 是否被排除
    exclude_reason Nullable(String),             -- 排除原因
    
    -- 白名單/排除名單判斷依據
    user_group_names Array(String),              -- 該員工的所有群組名稱
    has_whitelist_group UInt8,                   -- 是否有白名單群組
    has_exclude_group UInt8,                     -- 是否有排除群組
    
    -- NodeCodes 歸屬依據
    node_codes Array(String),                    -- 該員工的所有 NodeCodes
    
    -- Metadata
    _transform_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_transform_time)
ORDER BY (vx_type, plant, factory, emp_code)
SETTINGS index_granularity = 8192;
