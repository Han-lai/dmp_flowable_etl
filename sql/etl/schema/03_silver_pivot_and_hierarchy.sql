-- ========================================
-- 步驟 3: Silver Layer - Pivot & Hierarchy
-- 內容: VarInst Pivot, Five Level Dimension
-- 前置: 01_bronze_flowable_core, 02_bronze_common_dims
-- ========================================

-- ========================================
-- 2.1 VARINST 透視表
-- ========================================
-- ========================================
-- 2.1 VARINST 透視表 (改為實體表以支援 Batch 寫入)
-- ========================================

-- DROP TABLE IF EXISTS silver.mv_varinst_pivoted;

-- Silver Layer: Variable Pivoted Table
-- 目的：將 BPM 流程中的動態變數攤平為結構化欄位，方便事實表進行維度過濾與鑽取
CREATE TABLE IF NOT EXISTS silver.mv_varinst_pivoted
(
    `PROC_INST_ID_` String,           -- 流程實例 ID (唯一識別碼)
    -- [業務維度欄位]
    `varinst_region` String,          -- 區域 (Manual Input)
    `varinst_plant` String,           -- 廠別 (Manual Input)
    `varinst_factory` String,         -- 工廠 (Manual Input)
    `varinst_lineName` String,        -- 線別名稱 (核心關聯維度)
    
    -- [業務變數 (11 欄)]
    `varinst_moNumber` String,        -- 工單號碼
    `varinst_modelName` String,       -- 機種名稱
    `varinst_deliveryArea` String,    -- 交付區域
    `varinst_scheduleNumber` String,  -- 排程編號
    `varinst_sapPlant` String,        -- SAP 廠別
    `varinst_sapProductGroup` String, -- SAP 產品組
    `varinst_pallet` String,          -- 棧板 ID
    `varinst_transferNo` String,      -- 轉單編號
    `varinst_qBlockEventId` String,   -- Q-Block 事件 ID
    `varinst_defectSn` String,        -- 不良品序號
    `varinst_time` String,            -- 介面自定義時間
    
    `varinst_autoComplete` String,    -- 自動完成旗標
    `_refresh_time` DateTime64(3)     -- 資料最後重新整理時間
)
ENGINE = ReplacingMergeTree(_refresh_time) -- 確保同一個流程 ID 僅保留最新變數狀態
ORDER BY PROC_INST_ID_                     -- 以流程 ID 排序，優化 Join 與 argMax 效能
TTL toDate(_refresh_time) + toIntervalYear(1) -- 資料保存期限：一年 (基於維護時間)
SETTINGS allow_nullable_key = 1, index_granularity = 8192;

-- -- 驗證
-- SELECT 'mv_varinst_pivoted' AS table_name, count() AS row_count 
-- FROM silver.mv_varinst_pivoted;

-- ========================================
-- 2.2 五階維度主檔 (修正 JOIN 邏輯)
-- 正確路徑: line_desc → prod_area → factory_area → mfg_site
-- ========================================
-- DROP TABLE IF EXISTS silver.mv_dim_mfg_five_level;

CREATE TABLE IF NOT EXISTS silver.mv_dim_mfg_five_level (
    line_name String,
    line_desc String,
    prod_area_code String,
    factory_code String,
    factory_name String,
    plant_code String,
    plant_name String,
    region_code String,
    region_name String,
    _mview_update_time DateTime64(3)
)
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (plant_code, line_name)
SETTINGS allow_nullable_key = 1;

-- 首次建立時，手動從來源生成資料
INSERT INTO silver.mv_dim_mfg_five_level
SELECT DISTINCT
    ld.LINE_NAME AS line_name,
    ld.LINE_DESC AS line_desc,
    pa.PROD_AREA_CODE AS prod_area_code,
    -- Factory Level (User Request: Use PM.MFG_PLANT_CODE)
    pm.MFG_PLANT_CODE AS factory_code,
    pm.MFG_PLANT_DESC AS factory_name,
    -- Plant Level (User Request: Use PM.FACTORY)
    pm.FACTORY AS plant_code,
    pm.FACTORY AS plant_name, -- Use Code as Name since no desc available in PM
    -- Region Level (Use MFG_SITE as region_code per user request 2026-02-04)
    fa.MFG_SITE AS region_code,
    sm.MFG_SITE_DESC AS region_name,
    now() AS _mview_update_time
FROM bronze.common_mdm_line_desc_master ld
LEFT JOIN bronze.common_mdm_prod_area_master pa ON ld.PROD_AREA_ID = pa.PROD_AREA_ID
-- FIX: Join to mfg_plant_master for correct Plant/Factory info (2026-02-03)
LEFT JOIN bronze.common_mdm_mfg_plant_master pm ON pa.MFG_PLANT_ID = pm.MFG_PLANT_ID
-- Keep FA join for Region info
LEFT JOIN bronze.common_mdm_factory_area_master fa ON pa.FACTORY = fa.FACTORY
LEFT JOIN bronze.common_mdm_mfg_site_master sm ON fa.MFG_SITE = sm.MFG_SITE
WHERE ld.LINE_NAME IS NOT NULL AND ld.LINE_NAME != '';
