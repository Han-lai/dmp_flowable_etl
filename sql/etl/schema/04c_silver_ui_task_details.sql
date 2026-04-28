-- ==========================================
-- Schema: UI Detail 專用明細寬表架構
-- 目的: 隔離 KPI 運算邏輯，獨立供應前端 31 欄明細需求
-- ==========================================

-- 1. 建立 UI 專用的轉置視圖 (View)
-- 包含原本 KPI 必須的變數，並額外擴充 9 個 UI 客製化變數
CREATE OR REPLACE VIEW silver.mv_ui_varinst_pivoted AS
SELECT 
    PROC_INST_ID_,
    -- 原有基礎變數
    max(case when NAME_ = 'moNumber' then TEXT_ end) as varinst_moNumber,
    max(case when NAME_ = 'region' then TEXT_ end) as varinst_region,
    max(case when NAME_ = 'plant' then TEXT_ end) as varinst_plant,
    max(case when NAME_ = 'factory' then TEXT_ end) as varinst_factory,
    max(case when NAME_ = 'lineName' then TEXT_ end) as varinst_lineName,
    max(case when NAME_ = 'autoComplete' then TEXT_ end) as varinst_autoComplete,
    
    -- ⬇️ 擴充的 9 個 UI 明細表專用變數 ⬇️
    max(case when NAME_ = 'sapPlant' then TEXT_ end) AS ui_sapPlant,
    max(case when NAME_ = 'sapProductGroup' then TEXT_ end) AS ui_sapProductGroup,
    max(case when NAME_ = 'pallet' then TEXT_ end) AS ui_pallet,
    max(case when NAME_ = 'transferNo' then TEXT_ end) AS ui_transferNo,
    max(case when NAME_ = 'qBlockEventId' then TEXT_ end) AS ui_qBlockEventId,
    max(case when NAME_ = 'defectSn' then TEXT_ end) AS ui_defectSn,
    max(case when NAME_ = 'modelName' then TEXT_ end) AS ui_modelName,
    max(case when NAME_ = 'deliveryArea' then TEXT_ end) AS ui_deliveryArea,
    max(case when NAME_ = 'scheduleNumber' then TEXT_ end) AS ui_scheduleNumber
FROM bronze.bpm_act_hi_varinst
GROUP BY PROC_INST_ID_;

-- 2. 建立全新的 UI 實體寬表 (Table)
-- 完全獨立於 silver.mv_fact_task_vx，保護 KPI 底層不被影響
CREATE TABLE IF NOT EXISTS silver.mv_fact_ui_task_details (
    -- [A] 任務基礎識別
    task_id String,
    proc_inst_id String,
    task_definition_key String,
    task_name String,
    l4_process_name String,          -- 來自 procdef.NAME_
    
    -- [B] 業務客製化變數 (含擴充的 9 個欄位)
    mo_number String,
    schedule_number String,          -- 來自 ui_scheduleNumber
    sap_plant String,                -- 來自 ui_sapPlant
    sap_product_group String,        -- 來自 ui_sapProductGroup
    pallet String,                   -- 來自 ui_pallet
    transfer_no String,              -- 來自 ui_transferNo
    qblock_event_id String,          -- 來自 ui_qBlockEventId
    defect_sn String,                -- 來自 ui_defectSn
    model_name String,               -- 來自 ui_modelName
    delivery_area String,            -- 來自 ui_deliveryArea
    
    -- [C] 製造五階與分類
    vx_type String,
    region String,
    plant String,
    factory String,
    line String,
    
    -- [D] 時間軸
    task_start_time DateTime,
    task_claim_time Nullable(DateTime),
    task_end_time Nullable(DateTime),
    
    -- [E] 執行者
    assignee_code String,
    assignee_name String,
    
    -- [F] 狀態與稽核
    task_status String,
    is_excluded UInt8,
    exclude_reason String,
    
    _mview_update_time DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (task_id);
