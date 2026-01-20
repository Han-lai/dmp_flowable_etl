-- ========================================
-- Silver 層 Materialized Views - 第一層（基礎聚合層）
-- ========================================
-- 用途：將複雜的 GROUP BY 聚合預先計算，提供給第二層 MVIEW 使用
-- 建立順序：必須在第二層 MVIEW 之前建立
-- 更新方式：Bronze 層資料變更時自動觸發更新

-- ========================================
-- 1. EAV 轉置 MVIEW - 流程變數聚合
-- ========================================
-- 將 ACT_HI_VARINST 的 EAV 結構轉為寬表格式
-- 提取常用的流程變數：moNumber, plant, factory, lineName

DROP TABLE IF EXISTS silver.mv_varinst_pivoted;

CREATE MATERIALIZED VIEW silver.mv_varinst_pivoted
ENGINE = ReplacingMergeTree()
ORDER BY (PROC_INST_ID_)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT 
    PROC_INST_ID_,
    MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber,
    MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS varinst_plant,
    MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS varinst_factory,
    MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS varinst_lineName,
    MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS varinst_region,
    now64(3) AS _mview_update_time
FROM bronze.bpm_act_hi_varinst
WHERE NAME_ IN ('moNumber', 'plant', 'factory', 'lineName', 'region')
GROUP BY PROC_INST_ID_;

-- ========================================
-- 2. 用戶群組聚合 MVIEW
-- ========================================
-- 將每個員工的所有 UserGroup 聚合，並預計算白名單/排除標記

DROP TABLE IF EXISTS silver.mv_emp_user_groups;

CREATE MATERIALIZED VIEW silver.mv_emp_user_groups
ENGINE = ReplacingMergeTree()
ORDER BY (EmpCode)
POPULATE
AS
SELECT 
    eug.EmpCode,
    groupArray(ug.UserGroupName) AS user_group_names,
    
    -- 預計算白名單標記
    hasAny(groupArray(ug.UserGroupName), ['User', 'PMUser', 'PowerUser']) AS has_whitelist_group,
    
    -- 預計算排除標記
    hasAny(groupArray(ug.UserGroupName), ['ManagerUser', 'LocalAdmin', 'GlobalAdmin', 'SystemAdmin', 'InternalAudit', 'SeniorOfficers&DTO']) AS has_exclude_group,
    
    -- 預計算具體群組標記（用於快速判斷）
    has(groupArray(ug.UserGroupName), 'User') AS has_user_group,
    has(groupArray(ug.UserGroupName), 'PMUser') AS has_pmuser_group,
    has(groupArray(ug.UserGroupName), 'PowerUser') AS has_poweruser_group,
    has(groupArray(ug.UserGroupName), 'ManagerUser') AS has_manageruser_group,
    
    length(groupArray(ug.UserGroupName)) AS user_group_count,
    now64(3) AS _mview_update_time
    
FROM bronze.common_emp_user_group_mapping eug
INNER JOIN bronze.common_user_group ug ON eug.UserGroupId = ug.UserGroupId
GROUP BY eug.EmpCode;

-- ========================================
-- 3. 員工節點聚合 MVIEW
-- ========================================
-- 將每個員工的所有 NodeCode 聚合，並預計算 Vx 歸屬標記

DROP TABLE IF EXISTS silver.mv_emp_node_codes;

CREATE MATERIALIZED VIEW silver.mv_emp_node_codes
ENGINE = ReplacingMergeTree()
ORDER BY (EmpCode)
POPULATE
AS
SELECT 
    EmpCode,
    groupArray(NodeCode) AS node_codes,
    
    -- 預計算 Vx 節點標記
    arrayExists(x -> x LIKE 'V1\\_%', groupArray(NodeCode)) AS has_v1_node,
    arrayExists(x -> x LIKE 'V2\\_%', groupArray(NodeCode)) AS has_v2_node,
    arrayExists(x -> x LIKE 'V3\\_%', groupArray(NodeCode)) AS has_v3_node,
    
    -- 統計各 Vx 節點數量
    length(arrayFilter(x -> x LIKE 'V1\\_%', groupArray(NodeCode))) AS v1_node_count,
    length(arrayFilter(x -> x LIKE 'V2\\_%', groupArray(NodeCode))) AS v2_node_count,
    length(arrayFilter(x -> x LIKE 'V3\\_%', groupArray(NodeCode))) AS v3_node_count,
    
    length(groupArray(NodeCode)) AS total_node_count,
    now64(3) AS _mview_update_time
    
FROM bronze.common_emp_node_role_mapping
GROUP BY EmpCode;

-- ========================================
-- 4. 員工組織資訊聚合 MVIEW
-- ========================================
-- 整合員工的組織資訊，包含 Plant/Factory 對應

DROP TABLE IF EXISTS silver.mv_emp_org_info;

CREATE MATERIALIZED VIEW silver.mv_emp_org_info
ENGINE = ReplacingMergeTree()
ORDER BY (EmpCode)
POPULATE
AS
SELECT 
    eoi.EmpCode,
    eoi.Plant,
    eoi.MFGFactoryId,
    
    -- 使用 MDM 主檔取得標準化的 Factory 代碼
    COALESCE(mpm.MFG_PLANT_CODE, eoi.MFGFactoryId) AS factory_code,
    
    -- NPE 判斷（用於 V3 → V1 特殊規則）
    CASE WHEN COALESCE(mpm.MFG_PLANT_CODE, eoi.MFGFactoryId) LIKE '%NPE%' THEN 1 ELSE 0 END AS is_npe_factory,
    
    now64(3) AS _mview_update_time
    
FROM bronze.common_emp_org_info_mapping eoi
LEFT JOIN bronze.common_mdm_mfg_plant_master mpm ON eoi.MFGFactoryId = mpm.MFG_PLANT_ID;

-- ========================================
-- 5. 任務狀態轉換聚合 MVIEW（可選）
-- ========================================
-- 預計算任務狀態相關的統計，用於效能優化

DROP TABLE IF EXISTS silver.mv_task_status_summary;

CREATE MATERIALIZED VIEW silver.mv_task_status_summary
ENGINE = SummingMergeTree()
ORDER BY (task_create_date, plant, factory, line, task_status, task_bypass)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT 
    toDate(TaskCreateTime) AS task_create_date,
    Plant AS plant,
    Factory AS factory,
    Line AS line,
    TaskStatus AS task_status,
    TaskBypass AS task_bypass,
    substring(TaskDefinitionKey, 1, 2) AS task_def_prefix,
    
    -- 統計指標
    count() AS task_count,
    countIf(TaskStatus = 'TODO') AS todo_count,
    countIf(TaskStatus = 'DOING') AS doing_count,
    countIf(TaskStatus = 'DONE') AS done_count,
    
    -- 排除條件統計
    countIf(TaskBypass != 'N') AS bypass_count,
    countIf(TaskDefinitionKey LIKE 'E%') AS e_prefix_count,
    countIf(TaskDefinitionKey LIKE 'C%') AS c_prefix_count,
    
    now64(3) AS _mview_update_time
    
FROM bronze.common_flowable_task_stats
WHERE TaskId IS NOT NULL AND TaskId != ''
GROUP BY 
    task_create_date,
    plant,
    factory, 
    line,
    task_status,
    task_bypass,
    task_def_prefix;

-- ========================================
-- 建立完成提示
-- ========================================
SELECT 'Silver Layer 1 MViews Created Successfully' AS status,
       'Next: Run 12_create_silver_mviews_layer2.sql' AS next_step;