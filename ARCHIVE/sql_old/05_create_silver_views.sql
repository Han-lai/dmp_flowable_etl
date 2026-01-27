-- ============================================
-- Silver Layer Views 建立腳本
-- ============================================

-- ============================================
-- 0. V_PROC_VARIABLES_PIVOTED - 流程變數樞紐 View
-- Grain: 一個 PROC_INST_ID_ = 一列
-- 用途: 將 varinst 的行轉列，方便後續 JOIN
-- 對齊參考環境: silver_proc_variables_pivoted
-- ============================================
DROP VIEW IF EXISTS silver.V_PROC_VARIABLES_PIVOTED;
CREATE VIEW silver.V_PROC_VARIABLES_PIVOTED AS
SELECT
    PROC_INST_ID_ AS PROC_INST_ID,
    anyIf(TEXT_, NAME_ = 'plant') AS PLANT,
    anyIf(TEXT_, NAME_ = 'factory') AS FACTORY,
    anyIf(TEXT_, NAME_ = 'region') AS REGION,
    anyIf(TEXT_, NAME_ = 'sapPlant') AS SAP_PLANT,
    anyIf(TEXT_, NAME_ = 'sapProductGroup') AS SAP_PROD_GRP,
    anyIf(TEXT_, NAME_ = 'lineName') AS LINE_NAME,
    anyIf(TEXT_, NAME_ = 'modelName') AS MODEL_NAME,
    anyIf(TEXT_, NAME_ = 'moNumber') AS MO_NUMBER,
    anyIf(TEXT_, NAME_ = 'scheduleNumber') AS SCH_NUMBER,
    anyIf(TEXT_, NAME_ = 'initiator') AS INITIATOR,
    anyIf(TEXT_, NAME_ = '_PROCESS_NODE_INFO') AS PROC_NODE_INFO,
    min(CREATE_TIME_) AS FIRST_VAR_CREATED_AT,
    max(LAST_UPDATED_TIME_) AS LAST_VAR_UPDATED_AT
FROM bronze.bpm_act_hi_varinst
WHERE NAME_ IN ('plant', 'factory', 'region', 'sapPlant', 'sapProductGroup', 
                'lineName', 'modelName', 'moNumber', 'scheduleNumber', 
                'initiator', '_PROCESS_NODE_INFO')
  AND PROC_INST_ID_ IS NOT NULL
  AND TASK_ID_ IS NULL
GROUP BY PROC_INST_ID_;


-- ============================================
-- 0.1 V_TASK_VARIABLES_PIVOTED - 任務變數樞紐 View (新增)
-- Grain: 一個 TASK_ID_ = 一列
-- 用途: 將任務層 varinst 的行轉列
-- 對齊參考環境: silver_task_variables_pivoted
-- ============================================
DROP VIEW IF EXISTS silver.V_TASK_VARIABLES_PIVOTED;
CREATE VIEW silver.V_TASK_VARIABLES_PIVOTED AS
SELECT
    TASK_ID_ AS TASK_ID,
    PROC_INST_ID_ AS PROC_INST_ID,
    anyIf(TEXT_, NAME_ = 'candidateUser') AS TASK_CANDIDATE_USER,
    anyIf(TEXT_, NAME_ = 'autoComplete') AS TASK_AUTO_COMPLETE,
    min(CREATE_TIME_) AS FIRST_VAR_CREATED_AT,
    max(LAST_UPDATED_TIME_) AS LAST_VAR_UPDATED_AT
FROM bronze.bpm_act_hi_varinst
WHERE NAME_ IN ('candidateUser', 'autoComplete')
  AND TASK_ID_ IS NOT NULL
GROUP BY TASK_ID_, PROC_INST_ID_;


-- ============================================
-- 1. V_HI_PROC_TASK_NODE - 任務節點 View
-- Grain: 一個 Task ID = 一列
-- 來源: taskinst + procinst + proc_variables + task_variables + identitylink + procdef + employee
-- 對齊參考環境: silver_enriched_taskinst + gold_proc_task_node
-- ============================================
DROP VIEW IF EXISTS silver.V_HI_PROC_TASK_NODE;
CREATE VIEW silver.V_HI_PROC_TASK_NODE AS
SELECT
    t.ID_ AS TASK_ID,
    t.PROC_INST_ID_ AS PROC_INST_ID,
    t.PROC_DEF_ID_ AS PROC_DEF_ID,
    t.TASK_DEF_KEY_ AS TASK_DEF_KEY,
    t.NAME_ AS TASK_NAME,
    t.ASSIGNEE_ AS ASSIGNEE,
    t.START_TIME_ AS START_TIME,
    t.CLAIM_TIME_ AS CLAIM_TIME,
    t.END_TIME_ AS END_TIME,
    t.DURATION_ AS DURATION_MS,
    t.DELETE_REASON_ AS DELETE_REASON,
    p.BUSINESS_KEY_ AS BUSINESS_KEY,
    
    -- 派生欄位：時長計算
    if(t.CLAIM_TIME_ IS NOT NULL, dateDiff('second', t.START_TIME_, t.CLAIM_TIME_), NULL) AS IDLE_DURATION_SEC,
    if(t.CLAIM_TIME_ IS NOT NULL AND t.END_TIME_ IS NOT NULL, dateDiff('second', t.CLAIM_TIME_, t.END_TIME_), NULL) AS WORK_DURATION_SEC,
    if(t.END_TIME_ IS NOT NULL, dateDiff('second', t.START_TIME_, t.END_TIME_), NULL) AS TOTAL_DURATION_SEC,
    
    -- 派生欄位：任務狀態 (對齊參考環境邏輯)
    multiIf(
        t.DELETE_REASON_ IS NOT NULL AND t.DELETE_REASON_ != '', 'CANCELLED',
        t.ASSIGNEE_ IS NULL AND t.END_TIME_ IS NULL, 'TODO',
        t.ASSIGNEE_ IS NOT NULL AND t.END_TIME_ IS NULL, 'DOING',
        t.ASSIGNEE_ IS NOT NULL AND t.CLAIM_TIME_ IS NULL AND t.END_TIME_ IS NOT NULL, 'DONE_AUTO',
        t.END_TIME_ IS NOT NULL, 'DONE',
        'TODO'
    ) AS TASK_STATUS,
    
    -- 派生欄位：是否自動完成 (來自任務變數)
    if(tv.TASK_AUTO_COMPLETE = '1', 'Y', 'N') AS TASK_BYPASS,
    
    -- 任務層變數
    tv.TASK_CANDIDATE_USER,
    tv.TASK_AUTO_COMPLETE,
    
    -- 候選人列表 (來自 identitylink，對齊參考環境)
    il.CANDIDATE_USERS_LINK,
    
    -- 流程層變數
    v.PLANT,
    v.FACTORY,
    v.REGION,
    v.SAP_PLANT,
    v.SAP_PROD_GRP,
    v.LINE_NAME,
    v.MODEL_NAME,
    v.MO_NUMBER,
    v.SCH_NUMBER,
    
    -- 流程定義
    pd.NAME_ AS PROC_DEF_NAME,
    pd.KEY_ AS PROC_DEF_KEY,
    
    -- 員工資訊
    e.DeptCodeLname AS DEPT_NAME

FROM bronze.bpm_act_hi_taskinst AS t
LEFT JOIN bronze.bpm_act_hi_procinst AS p ON t.PROC_INST_ID_ = p.PROC_INST_ID_
LEFT JOIN silver.V_PROC_VARIABLES_PIVOTED AS v ON t.PROC_INST_ID_ = v.PROC_INST_ID
LEFT JOIN silver.V_TASK_VARIABLES_PIVOTED AS tv ON t.ID_ = tv.TASK_ID
LEFT JOIN (
    SELECT 
        TASK_ID_,
        groupArray(USER_ID_) AS CANDIDATE_USERS_LINK
    FROM bronze.bpm_act_hi_identitylink
    WHERE TYPE_ = 'candidate' AND USER_ID_ IS NOT NULL
    GROUP BY TASK_ID_
) AS il ON t.ID_ = il.TASK_ID_
LEFT JOIN bronze.bpm_act_re_procdef AS pd ON t.PROC_DEF_ID_ = pd.ID_
LEFT JOIN bronze.common_hr_employee AS e ON t.ASSIGNEE_ = e.EmpCode;


-- ============================================
-- 2. V_HI_PROCINST_NODE - 流程實例 View
-- Grain: 一個 PROC_INST_ID_ = 一列
-- 來源: procinst + proc_variables + procdef
-- 對齊參考環境: silver_enriched_procinst + gold_procinst_node
-- ============================================
DROP VIEW IF EXISTS silver.V_HI_PROCINST_NODE;
CREATE VIEW silver.V_HI_PROCINST_NODE AS
SELECT
    p.ID_ AS ID,
    p.PROC_INST_ID_ AS PROC_INST_ID,
    p.BUSINESS_KEY_ AS BUSINESS_KEY,
    p.PROC_DEF_ID_ AS PROC_DEF_ID,
    p.START_TIME_ AS START_TIME,
    p.END_TIME_ AS END_TIME,
    p.DURATION_ AS DURATION_MS,
    p.START_USER_ID_ AS START_USER_ID,
    p.START_ACT_ID_ AS START_ACT_ID,
    p.END_ACT_ID_ AS END_ACT_ID,
    p.SUPER_PROCESS_INSTANCE_ID_ AS SUPER_ID,
    p.DELETE_REASON_ AS DELETE_REASON,
    p.TENANT_ID_ AS TENANT_ID,
    p.NAME_ AS NAME,
    p.BUSINESS_STATUS_ AS BUSINESS_STATUS,
    
    -- 派生欄位：流程總歷時（秒）
    if(p.DURATION_ IS NOT NULL, toInt64(p.DURATION_) / 1000, NULL) AS DURATION_SEC,
    
    -- 派生欄位：是否完成
    if(p.END_TIME_ IS NOT NULL, 1, 0) AS IS_COMPLETED,
    
    -- 派生欄位：流程狀態 (對齊參考環境: TERMINATED/RUNNING/COMPLETED -> TERMINATED/DOING/DONE)
    multiIf(
        p.DELETE_REASON_ IS NOT NULL AND p.DELETE_REASON_ != '', 'TERMINATED',
        p.END_TIME_ IS NOT NULL, 'DONE',
        'DOING'
    ) AS PROC_STATE,
    
    -- 派生欄位：階層深度
    if(p.SUPER_PROCESS_INSTANCE_ID_ IS NULL OR p.SUPER_PROCESS_INSTANCE_ID_ = '', 1, 2) AS DEPTH,
    
    -- 流程層變數
    v.PLANT,
    v.FACTORY,
    v.REGION,
    v.SAP_PLANT,
    v.SAP_PROD_GRP,
    v.LINE_NAME,
    v.MODEL_NAME,
    v.MO_NUMBER,
    v.SCH_NUMBER,
    v.INITIATOR,
    v.PROC_NODE_INFO,
    
    -- 流程定義
    pd.NAME_ AS PROC_DEF_NAME,
    pd.KEY_ AS PROC_DEF_KEY,
    pd.VERSION_ AS PROC_DEF_VERSION

FROM bronze.bpm_act_hi_procinst AS p
LEFT JOIN silver.V_PROC_VARIABLES_PIVOTED AS v ON p.PROC_INST_ID_ = v.PROC_INST_ID
LEFT JOIN bronze.bpm_act_re_procdef AS pd ON p.PROC_DEF_ID_ = pd.ID_;


-- ============================================
-- 3. V_HI_BIZ_EVENT_INFO - 業務事件 View
-- Grain: 一個 BUSINESS_KEY_ = 一列
-- 來源: procinst (GROUP BY) + taskinst (子查詢) + procdef
-- ============================================
DROP VIEW IF EXISTS silver.V_HI_BIZ_EVENT_INFO;
CREATE VIEW silver.V_HI_BIZ_EVENT_INFO AS
SELECT
    p.BUSINESS_KEY AS BIZ_EVENT_KEY,
    p.FIRST_START_TIME,
    p.FINAL_END_TIME,
    p.TOTAL_DURATION_SEC,
    p.TOTAL_PROC_DURATION_SEC,
    p.PROCESS_COUNT,
    p.IS_IN_PROGRESS,
    p.FIRST_PROC_DEF_NAME,
    coalesce(t.TASK_TODO_CNT, 0) AS TASK_TODO_CNT,
    coalesce(t.TASK_DOING_CNT, 0) AS TASK_DOING_CNT,
    coalesce(t.TASK_DONE_CNT, 0) AS TASK_DONE_CNT,
    coalesce(t.TASK_AUTOCOMPLETE_CNT, 0) AS TASK_AUTOCOMPLETE_CNT,
    coalesce(t.TASK_CANCELLED_CNT, 0) AS TASK_CANCELLED_CNT,
    coalesce(t.TOTAL_WORK_DURATION_SEC, 0) AS TOTAL_WORK_DURATION_SEC
FROM (
    SELECT
        pi.BUSINESS_KEY_ AS BUSINESS_KEY,
        min(pi.START_TIME_) AS FIRST_START_TIME,
        if(countIf(pi.END_TIME_ IS NULL) = 0, max(pi.END_TIME_), NULL) AS FINAL_END_TIME,
        if(countIf(pi.END_TIME_ IS NULL) = 0, dateDiff('second', min(pi.START_TIME_), max(pi.END_TIME_)), NULL) AS TOTAL_DURATION_SEC,
        sum(if(pi.DURATION_ IS NOT NULL, toInt64(pi.DURATION_) / 1000, 0)) AS TOTAL_PROC_DURATION_SEC,
        count(*) AS PROCESS_COUNT,
        if(countIf(pi.END_TIME_ IS NULL) > 0, 1, 0) AS IS_IN_PROGRESS,
        anyIf(pd.NAME_, pi.SUPER_PROCESS_INSTANCE_ID_ IS NULL OR pi.SUPER_PROCESS_INSTANCE_ID_ = '') AS FIRST_PROC_DEF_NAME
    FROM bronze.bpm_act_hi_procinst AS pi
    LEFT JOIN bronze.bpm_act_re_procdef AS pd ON pi.PROC_DEF_ID_ = pd.ID_
    WHERE pi.BUSINESS_KEY_ IS NOT NULL AND pi.BUSINESS_KEY_ != ''
    GROUP BY pi.BUSINESS_KEY_
) AS p
LEFT JOIN (
    SELECT
        pi.BUSINESS_KEY_ AS BUSINESS_KEY,
        countIf(ti.ASSIGNEE_ IS NULL AND ti.END_TIME_ IS NULL) AS TASK_TODO_CNT,
        countIf(ti.ASSIGNEE_ IS NOT NULL AND ti.END_TIME_ IS NULL) AS TASK_DOING_CNT,
        countIf(ti.END_TIME_ IS NOT NULL AND ti.CLAIM_TIME_ IS NOT NULL AND (ti.DELETE_REASON_ IS NULL OR ti.DELETE_REASON_ = '')) AS TASK_DONE_CNT,
        countIf(ti.ASSIGNEE_ IS NOT NULL AND ti.CLAIM_TIME_ IS NULL AND ti.END_TIME_ IS NOT NULL AND (ti.DELETE_REASON_ IS NULL OR ti.DELETE_REASON_ = '')) AS TASK_AUTOCOMPLETE_CNT,
        countIf(ti.DELETE_REASON_ IS NOT NULL AND ti.DELETE_REASON_ != '') AS TASK_CANCELLED_CNT,
        sum(if(ti.CLAIM_TIME_ IS NOT NULL AND ti.END_TIME_ IS NOT NULL, dateDiff('second', ti.CLAIM_TIME_, ti.END_TIME_), 0)) AS TOTAL_WORK_DURATION_SEC
    FROM bronze.bpm_act_hi_taskinst AS ti
    INNER JOIN bronze.bpm_act_hi_procinst AS pi ON ti.PROC_INST_ID_ = pi.PROC_INST_ID_
    WHERE pi.BUSINESS_KEY_ IS NOT NULL AND pi.BUSINESS_KEY_ != ''
    GROUP BY pi.BUSINESS_KEY_
) AS t ON p.BUSINESS_KEY = t.BUSINESS_KEY;
