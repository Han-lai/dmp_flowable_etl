-- ClickHouse Bronze 層表格建立模板
-- 時間精度標準：DateTime64(6) 以匹配 MSSQL datetime2(7)

CREATE TABLE bronze.{table_name}
(
    -- ===========================================
    -- 業務欄位區域 (依實際需求替換)
    -- ===========================================
    {business_columns},
    
    -- ===========================================
    -- 標準時間欄位 (必須包含)
    -- ===========================================
    _sync_time DateTime64(6) DEFAULT now64(6) COMMENT '資料同步時間戳',
    
    -- ===========================================
    -- 常用業務時間欄位範例
    -- ===========================================
    -- CreateDatetime Nullable(DateTime64(6)) COMMENT '建立時間',
    -- UpdateDatetime Nullable(DateTime64(6)) COMMENT '更新時間',
    -- ModifyDate Nullable(DateTime64(6)) COMMENT '修改日期',
    -- StartTime DateTime64(6) COMMENT '開始時間',
    -- EndTime Nullable(DateTime64(6)) COMMENT '結束時間'
)
ENGINE = MergeTree()
ORDER BY (_sync_time)
PARTITION BY toYYYYMM(_sync_time)
SETTINGS 
    -- Parts 管理設定 (防止 Parts 爆炸)
    parts_to_delay_insert = 150,
    parts_to_throw_insert = 300,
    -- 索引設定
    index_granularity = 8192;

-- ===========================================
-- 使用說明
-- ===========================================
-- 1. 替換 {table_name} 為實際表格名稱
-- 2. 替換 {business_columns} 為實際業務欄位定義
-- 3. 根據需要啟用常用時間欄位
-- 4. 確保所有時間欄位使用 DateTime64(6) 精度
-- 5. 可選：根據查詢模式調整 ORDER BY 和 PARTITION BY

-- ===========================================
-- 時間欄位型別對照表
-- ===========================================
-- MSSQL datetime2(7)     → ClickHouse DateTime64(6)
-- MSSQL datetime         → ClickHouse DateTime64(6) 
-- MSSQL smalldatetime    → ClickHouse DateTime64(6)
-- MSSQL date             → ClickHouse Date
-- MSSQL time             → ClickHouse String (需要特殊處理)

-- ===========================================
-- 範例：完整的表格定義
-- ===========================================
/*
CREATE TABLE bronze.example_table
(
    -- 主鍵欄位
    ID String COMMENT '主鍵',
    
    -- 業務欄位
    Name String COMMENT '名稱',
    Status String COMMENT '狀態',
    Amount Decimal(18,2) COMMENT '金額',
    
    -- 時間欄位 (使用標準精度)
    CreateDatetime Nullable(DateTime64(6)) COMMENT '建立時間',
    UpdateDatetime Nullable(DateTime64(6)) COMMENT '更新時間',
    
    -- 系統欄位
    _sync_time DateTime64(6) DEFAULT now64(6) COMMENT '同步時間'
)
ENGINE = MergeTree()
ORDER BY (ID, _sync_time)
PARTITION BY toYYYYMM(_sync_time)
SETTINGS 
    parts_to_delay_insert = 150,
    parts_to_throw_insert = 300,
    index_granularity = 8192;
*/