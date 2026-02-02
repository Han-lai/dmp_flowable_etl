-- ============================================
-- MSSQL vs ClickHouse 對齊驗證查詢
-- ============================================
-- 目標：產生與 MSSQL 完全一致的欄位和口徑
-- 基於您提供的 MSSQL 查詢邏輯重新建構

-- ClickHouse 查詢（對齊 MSSQL 口徑）
WITH 
-- 流程變數轉置（對齊 MSSQL 的多個 varinst LEFT JOIN）
proc_vars AS (
    SELECT 
        PROC_INST_ID_,
        anyIf(TEXT_, NAME_ = 'plant') AS plant,
        anyIf(TEXT_, NAME_ = 'factory') AS factory,
        anyIf(TEXT_, NAME_ = 'productionArea') AS productionArea,
        anyIf(TEXT_, NAME_ = 'lineName') AS lineName,
        anyIf(TEXT_, NAME_ = 'modelName') AS modelName,
        anyIf(TEXT_, NAME_ = 'deliveryArea') AS deliveryArea,
        anyIf(TEXT_, NAME_ = 'scheduleNumber') AS scheduleNumber,
        anyIf(TEXT_, NAME_ = 'moNumber') AS moNumber,
        anyIf(TEXT_, NAME_ = 'sapPlant') AS sapPlant,
        anyIf(TEXT_, NAME_ = 'sapProductGroup') AS sapProductGroup,
        anyIf(TEXT_, NAME_ = 'pallet') AS pallet,
        anyIf(TEXT_, NAME_ = 'transferNo') AS transferNo,
        anyIf(TEXT_, NAME_ = 'qBlockEventId') AS qBlockEventId,
        anyIf(TEXT_, NAME_ = 'defectSn') AS defectSn,
        anyIf(TEXT_, NAME_ = 'time') AS timeKey
    FROM bronze.bpm_act_hi_varinst
    WHERE NAME_ IN ('plant', 'factory', 'productionArea', 'lineName', 'modelName', 
                    'deliveryArea', 'scheduleNumber', 'moNumber', 'sapPlant', 
                    'sapProductGroup', 'pallet', 'transferNo', 'qBlockEventId', 
                    'defectSn', 'time')
      AND TASK_ID_ IS NULL  -- 只取流程層變數
    GROUP BY PROC_INST_ID_
),

-- 任務變數轉置（對齊 MSSQL 的 task 層 varinst）
task_vars AS (
    SELECT 
        TASK_ID_,
        anyIf(LONG_, NAME_ = 'autoComplete') AS autoComplete_flag
    FROM bronze.bmp_act_hi_varinst
    WHERE NAME_ = 'autoComplete'
      AND TASK_ID_ IS NOT NULL
    GROUP BY TASK_ID_
)

SELECT
    -- 流程相關欄位
    hi.PROC_INST_ID_ AS processInstanceId,
    pd.KEY_ AS processDefinitionKey,
    pd.NAME_ AS processDefinitionName,
    
    -- 流程變數欄位
    COALESCE(pv.plant, '') AS plant,
    COALESCE(pv.factory, '') AS factory,
    COALESCE(pv.productionArea, '') AS productionArea,
    COALESCE(pv.lineName, '') AS line,  -- 注意：MSSQL 用 line，但變數是 lineName
    COALESCE(pv.modelName, '') AS modelName,
    COALESCE(pv.deliveryArea, '') AS deliveryArea,
    COALESCE(pv.scheduleNumber, '') AS scheduleNumber,
    COALESCE(pv.moNumber, '') AS moNumber,
    COALESCE(pv.sapPlant, '') AS sapPlant,
    COALESCE(pv.sapProductGroup, '') AS sapProductGroup,
    COALESCE(pv.pallet, '') AS pallet,
    COALESCE(pv.transferNo, '') AS transferNo,
    COALESCE(pv.qBlockEventId, '') AS qBlockEventId,
    COALESCE(pv.defectSn, '') AS defectSn,
    COALESCE(pv.timeKey, '') AS timeKey,
    
    -- 任務相關欄位
    hti.ID_ AS taskId,
    hti.TASK_DEF_KEY_ AS taskDefinitionKey,
    hti.NAME_ AS taskName,
    
    -- 任務狀態（對齊 MSSQL 定義）
    CASE 
        WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
        WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
        ELSE 'TODO'
    END AS taskStatus,
    
    -- 任務 Bypass（對齊 MSSQL 定義）
    CASE 
        WHEN tv.autoComplete_flag = 1 THEN 'Y'
        ELSE 'N'
    END AS taskBypass,
    
    -- 人員資訊
    hti.ASSIGNEE_ AS taskAssignee,
    he.EmpCode AS taskAssigneeAccount,
    he.EmpName AS taskAssigneeName,
    
    -- 時間欄位
    hti.START_TIME_ AS taskCreateTime,
    hti.CLAIM_TIME_ AS taskClaimTime,
    hti.END_TIME_ AS taskEndTime,
    
    -- 時長計算（對齊 MSSQL 定義）
    -- taskDurationMinutes: START_TIME 到 END_TIME，如果沒結束就到 now()
    CASE 
        WHEN hti.END_TIME_ IS NOT NULL THEN 
            round(dateDiff('second', hti.START_TIME_, hti.END_TIME_) / 60.0, 2)
        ELSE 
            round(dateDiff('second', hti.START_TIME_, now()) / 60.0, 2)
    END AS taskDurationMinutes,
    
    -- taskWorkMinutes: CLAIM_TIME 到 END_TIME，如果沒結束就到 now()
    -- 如果 CLAIM_TIME 是 null，這欄位為 null（需確認 MSSQL 行為）
    CASE 
        WHEN hti.CLAIM_TIME_ IS NULL THEN NULL
        WHEN hti.END_TIME_ IS NOT NULL THEN 
            round(dateDiff('second', hti.CLAIM_TIME_, hti.END_TIME_) / 60.0, 2)
        ELSE 
            round(dateDiff('second', hti.CLAIM_TIME_, now()) / 60.0, 2)
    END AS taskWorkMinutes,
    
    -- 其他欄位
    hti.DELETE_REASON_ AS deleteReason

FROM bronze.bpm_act_hi_procinst hi
LEFT JOIN bronze.bpm_act_hi_taskinst hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
LEFT JOIN bronze.bpm_act_re_procdef pd ON hi.PROC_DEF_ID_ = pd.ID_
LEFT JOIN proc_vars pv ON hi.PROC_INST_ID_ = pv.PROC_INST_ID_
LEFT JOIN task_vars tv ON hti.ID_ = tv.TASK_ID_
LEFT JOIN bronze.common_hr_employee he ON hti.ASSIGNEE_ = he.EmpCode

-- 時間篩選（對齊 MSSQL 口徑）
-- 只要任務的 START_TIME 或 CLAIM_TIME 或 END_TIME 任一時間落在區間內就納入
WHERE (
    (hti.START_TIME_ >= '2026-01-01 00:00:00' AND hti.START_TIME_ < '2026-01-02 00:00:00')
    OR (hti.CLAIM_TIME_ >= '2026-01-01 00:00:00' AND hti.CLAIM_TIME_ < '2026-01-02 00:00:00')
    OR (hti.END_TIME_ >= '2026-01-01 00:00:00' AND hti.END_TIME_ < '2026-01-02 00:00:00')
)

-- 測試特定 sample row
-- AND hi.PROC_INST_ID_ = 'c334aa74-e661-11f0-87ac-9a7dcf9ebdcc'
-- AND hti.ID_ = 'c34aca98-e661-11f0-87ac-9a7dcf9ebdcc'

ORDER BY hi.PROC_INST_ID_, hti.ID_;