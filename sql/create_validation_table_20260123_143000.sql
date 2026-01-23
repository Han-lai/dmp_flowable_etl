-- ============================================
-- ClickHouse 驗證表格建立腳本
-- 用途：建立與 MSSQL Reference Query 結果一致的驗證表格
-- 建立時間: 2026-01-23 14:30:00
-- ============================================

-- 建立 validation database
CREATE DATABASE IF NOT EXISTS validation;

-- 刪除舊表格
DROP TABLE IF EXISTS validation.mssql_reference_l5_tasks;

-- 建立驗證表格，Schema 與 MSSQL 查詢結果完全一致
CREATE TABLE validation.mssql_reference_l5_tasks
(
    processInstanceId String,
    processDefinitionKey Nullable(String),
    processDefinitionName Nullable(String),
    plant Nullable(String),
    factory Nullable(String),
    productionArea Nullable(String),
    line Nullable(String),
    modelName Nullable(String),
    deliveryArea Nullable(String),
    scheduleNumber Nullable(String),
    moNumber Nullable(String),
    sapPlant Nullable(String),
    sapProductGroup Nullable(String),
    pallet Nullable(String),
    transferNo Nullable(String),
    qBlockEventId Nullable(String),
    defectSn Nullable(String),
    timeKey Nullable(String),
    taskId String,
    taskDefinitionKey Nullable(String),
    taskName Nullable(String),
    taskStatus Nullable(String),
    taskBypass Nullable(String),
    taskAssignee Nullable(String),
    taskAssigneeAccount Nullable(String),
    taskAssigneeName Nullable(String),
    taskCreateTime Nullable(String),
    taskClaimTime Nullable(String),
    taskEndTime Nullable(String),
    taskDurationMinutes Nullable(Float64),
    taskWorkMinutes Nullable(Float64),
    deleteReason Nullable(String),
    -- Metadata
    _import_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree()
ORDER BY (taskId);

-- ============================================
-- 手動插入 MSSQL Reference 資料 (2025-12-25 WJ2/NBU/E5)
-- ============================================

INSERT INTO validation.mssql_reference_l5_tasks 
(processInstanceId, processDefinitionKey, processDefinitionName, plant, factory, productionArea, line, modelName, deliveryArea, scheduleNumber, moNumber, sapPlant, sapProductGroup, pallet, transferNo, qBlockEventId, defectSn, timeKey, taskId, taskDefinitionKey, taskName, taskStatus, taskBypass, taskAssignee, taskAssigneeAccount, taskAssigneeName, taskCreateTime, taskClaimTime, taskEndTime, taskDurationMinutes, taskWorkMinutes, deleteReason)
VALUES
('1178d911-e0aa-11f0-8766-badd3bc212ac', 'V3_5_3_9', '3.5.3.9 Finished Product Inspection & Release', 'WJ2', 'NBU', 'WJ2_NBU_MAIN', 'E5', 'ADP-140FB BA', '', '', '20251224112', '', '', 'P2U092512240093', '', '', '', '_', '117c3488-e0aa-11f0-8766-badd3bc212ac', 'V3_5_3_9_1', '3.5.3.9.1 Execute Final Product Inspection and Release', 'DOING', 'N', '56629210', 'HUINJ.ZHAO', '趙暉', '2025-12-24 17:22:29', '2025-12-25 11:51:38', '', 43163.67, 42054.52, ''),
('a83fa1af-e124-11f0-8766-badd3bc212ac', 'V3_5_1_10', '3.5.1.10 Resource Allocation', 'WJ2', 'NBU', 'WJ2_NBU_MAIN', 'E5', 'ADP-45DG BB', '', '000058851982', '3152506536', '', '', '', '', '', '', '_', 'a84b6195-e124-11f0-8766-badd3bc212ac', 'V3_5_1_10_1', '3.5.1.10.1 Call Resources', 'TODO', 'N', '', '', '', '2025-12-25 08:00:00', '', '', 42286.15, NULL, ''),
('a8c8a825-e124-11f0-8766-badd3bc212ac', 'V3_5_1_10', '3.5.1.10 Resource Allocation', 'WJ2', 'NBU', 'WJ2_NBU_MAIN', 'E5', 'ADP-65KE BA', '', '000058852719', '3152506697', '', '', '', '', '', '', '_', 'a8cf860b-e124-11f0-8766-badd3bc212ac', 'V3_5_1_10_1', '3.5.1.10.1 Call Resources', 'TODO', 'N', '', '', '', '2025-12-25 08:00:01', '', '', 42286.13, NULL, ''),
('a9607bab-e124-11f0-8766-badd3bc212ac', 'V3_5_1_10', '3.5.1.10 Resource Allocation', 'WJ2', 'NBU', 'WJ2_NBU_MAIN', 'E5', 'ADP-65AE BA', '', '000058852838', '3152506743', '', '', '', '', '', '', '_', 'a96360f1-e124-11f0-8766-badd3bc212ac', 'V3_5_1_10_1', '3.5.1.10.1 Call Resources', 'TODO', 'N', '', '', '', '2025-12-25 08:00:02', '', '', 42286.12, NULL, ''),
('dc9cab8e-e155-11f0-8766-badd3bc212ac', 'V3_5_1_0', '3.5.1.0 Process Check', 'WJ2', 'NBU', 'WJ2_NBU_MAIN', 'E5', 'ADP-65KE BA', '', '000058851564', '3152506512', '', '', '', '', '', '', '_', 'dc9fb8e2-e155-11f0-8766-badd3bc212ac', 'V3_5_1_0_1', '3.5.1.0.1 MFG Check Model Requirements', 'TODO', 'N', '', '', '', '2025-12-25 13:52:13', '', '', 41933.93, NULL, '');

-- ============================================
-- 驗證查詢
-- ============================================

-- 檢查插入結果
SELECT 
    '驗證表格記錄數' as check_type,
    COUNT(*) as record_count
FROM validation.mssql_reference_l5_tasks;

-- 顯示所有記錄
SELECT * FROM validation.mssql_reference_l5_tasks ORDER BY taskCreateTime;

-- ============================================
-- 比對查詢範例
-- ============================================

-- 與 Bronze 層比對
SELECT 
    'Bronze vs Reference' as comparison,
    b.taskId,
    b.taskStatus as bronze_status,
    r.taskStatus as reference_status,
    b.taskCreateTime as bronze_create_time,
    r.taskCreateTime as reference_create_time
FROM bronze.bmp_act_hi_taskinst b
FULL OUTER JOIN validation.mssql_reference_l5_tasks r
    ON b.ID_ = r.taskId
WHERE toDate(b.START_TIME_) = '2025-12-25'
   OR r.taskId IS NOT NULL;

-- 與 Silver 層比對 (檢查資料膨脹問題)
SELECT 
    'Silver Record Count Check' as check_type,
    COUNT(*) as silver_count,
    (SELECT COUNT(*) FROM validation.mssql_reference_l5_tasks) as reference_count,
    COUNT(*) - (SELECT COUNT(*) FROM validation.mssql_reference_l5_tasks) as difference
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE toDate(task_create_time) = '2025-12-25'
AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5';