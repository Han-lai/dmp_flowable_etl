-- ========================================
-- 步驟 4: Silver Layer - Fact Tasks (V4.3 Super Silver 版)
-- 內容: 核心任務事實表，包含 L4 資訊、時效指標、11 個業務變數與週期結算標籤
-- 前置: 03_silver_pivot_and_hierarchy
-- ========================================
-- Silver Fact Table: Unified Source of Truth (V4.3 Super Silver)
-- 目的：存儲最精細的任務執行紀錄，作為所有 KPI 指標、明細報表與鑽取分析的唯一來源

CREATE TABLE IF NOT EXISTS silver.mv_fact_task_vx
(
    -- [A] 識別資訊 (Identification)
    `task_id` String,                 -- 任務 ID (物理主鍵)
    `proc_inst_id` String,            -- 流程實例 ID
    `l4_process_id` String,           -- L4 流程編號 (業務狀態代碼)
    `l4_process_name` String,         -- L4 流程名稱
    `task_definition_key` String,     -- 任務定義 Key (用於邏輯分類)
    `task_name` String,               -- 任務顯示名稱
    
    -- [B] 時間維度 (Time Dimensions)
    `task_start_time` DateTime,       -- 任務開始時間 (開單)
    `task_claim_time` Nullable(DateTime), -- 簽收時間
    `task_end_time` Nullable(DateTime),   -- 完成時間
    `task_start_date` Date,           -- 開始日期
    `task_claim_date` Nullable(Date), -- 簽收日期
    `task_end_date` Nullable(Date),   -- 完成日期
    `task_primary_date` Date,         -- 主基準日期 (用於分區與 KPI 錨定)
    `task_create_date` Date,          -- 資料建立日期
    
    -- [C] 效能指標 (Performance Metrics)
    `duration_min` Nullable(Float64), -- 總持續時間 (分鐘)
    `processing_time_min` Nullable(Float64), -- 實際處理時間 (分鐘)
    `ui_time_field` String,           -- 介面自定義時間
    
    -- [D] 結算狀態 (Cohort Labels)
    `task_status` String,             -- 當前最新狀態 (TODO/DOING/DONE)
    `status_daily` String,            -- 日結算狀態 (Cohort)
    `status_weekly` String,           -- 週結算狀態 (Cohort)
    `status_monthly` String,          -- 月結算狀態 (Cohort)
    
    -- [E] 製造維度 (Manufacturing Dimensions)
    `vx_type` String,                 -- 業務分類 (V1/V2/V3)
    `region` String,                  -- 區域
    `plant` String,                   -- 廠別
    `factory` String,                 -- 工廠
    `line` String,                    -- 線別
    
    -- [F] 業務變數 (Business Variables - 11 欄)
    `mo_number` String,               -- 工單號
    `model_name` String,              -- 機種
    `delivery_area` String,           -- 交付區域
    `schedule_number` String,         -- 排程編號
    `sap_plant` String,               -- SAP 廠別
    `sap_product_group` String,       -- SAP 產品組
    `pallet` String,                  -- 棧板
    `transfer_no` String,             -- 轉單編號
    `qblock_event_id` String,         -- Q-Block ID
    `defect_sn` String,               -- 不良品 SN
    
    -- [G] 排除與稽核 (Exclusion & Audit)
    `is_excluded` UInt8,              -- 是否排除 (1=Yes, 0=No)
    `exclude_reason` String,          -- 排除原因描述
    `assignee_code` String,           -- 處理人代碼
    `assignee_name` String,           -- 處理人姓名
    
    `_mview_update_time` DateTime64(3) -- 系統更新時間
)
ENGINE = ReplacingMergeTree(_mview_update_time) -- 確保同一個 task_id 僅保留最新版本
PARTITION BY toYYYYMM(task_primary_date)        -- 按月分區，優化檢索與資料管理
ORDER BY task_id                                -- 按任務 ID 排序，優化去重效能
TTL task_primary_date + toIntervalYear(1)       -- 資料保存期限：一年
SETTINGS allow_nullable_key = 1, index_granularity = 8192; -- 允許 nullable key 與調整索引粒度
