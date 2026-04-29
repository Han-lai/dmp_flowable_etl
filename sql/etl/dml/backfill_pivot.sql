-- Phase 1: Dimension Pivot (Time-Bounded)
-- Table: silver.mv_varinst_pivoted
WITH target_procs AS (
    -- [效能優化]：僅處理目前任務回填視窗內涉及到的流程 ID，避免對歷史全量變數表進行全掃描
    SELECT DISTINCT PROC_INST_ID_
    FROM bronze.bpm_act_hi_taskinst
    WHERE (START_TIME_ >= '{start_ts}' AND START_TIME_ <= '{end_ts}')
       OR (CLAIM_TIME_ >= '{start_ts}' AND CLAIM_TIME_ <= '{end_ts}')
       OR (END_TIME_ >= '{start_ts}' AND END_TIME_ <= '{end_ts}')
)
INSERT INTO silver.mv_varinst_pivoted
SELECT
    v.PROC_INST_ID_, -- 流程實例 ID (作為轉置後的主鍵)
    -- 使用 argMaxIf 取得每個流程 ID 在該時間視窗內最新版本的變數值 (REV_ 為版本標籤)
    -- 商業意義：流程執行過程中，人員可能會修正線別或工單號，我們僅保留最後一次更新的正確值
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'region') AS varinst_region, -- 區域 (如: CNE)
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'plant') AS varinst_plant, -- 廠別 (如: WJ2)
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'factory') AS varinst_factory, -- 工廠 (如: NBU)
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'lineName') AS varinst_lineName, -- 線別名稱 (與 MDM 對接的關鍵欄位)
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'moNumber') AS varinst_moNumber, -- 工單號碼
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'modelName') AS varinst_modelName, -- 機種名稱 (生產標的)
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'deliveryArea') AS varinst_deliveryArea, -- 交付區域
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'scheduleNumber') AS varinst_scheduleNumber, -- 排程編號
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'sapPlant') AS varinst_sapPlant, -- SAP 廠別編號
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'sapProductGroup') AS varinst_sapProductGroup, -- SAP 產品組
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'pallet') AS varinst_pallet, -- 棧板編號
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'transferNo') AS varinst_transferNo, -- 轉單編號
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'qBlockEventId') AS varinst_qBlockEventId, -- Q-Block 系統事件 ID
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'defectSn') AS varinst_defectSn, -- 不良品序號
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'time') AS varinst_time, -- 介面顯示時間
    argMaxIf(if(v.LONG_ = 1, 'true', 'false'), v.REV_, v.NAME_ = 'autoComplete') AS varinst_autoComplete, -- 自動完成標記 (1 表示該任務由系統自動觸發並跳過)
    now() AS _refresh_time -- 記錄該流程資料在同步時的最後時間戳記
FROM bronze.bpm_act_hi_varinst v
INNER JOIN target_procs t ON v.PROC_INST_ID_ = t.PROC_INST_ID_
WHERE v.NAME_ IN ('region', 'plant', 'factory', 'lineName', 'moNumber', 'autoComplete', 'modelName', 'deliveryArea', 'scheduleNumber', 'sapPlant', 'sapProductGroup', 'pallet', 'transferNo', 'qBlockEventId', 'defectSn', 'time')
  AND v.CREATE_TIME_ >= parseDateTimeBestEffort('{start_ts}') - INTERVAL 180 DAY
  AND v.CREATE_TIME_ <= '{end_ts}'
GROUP BY v.PROC_INST_ID_
