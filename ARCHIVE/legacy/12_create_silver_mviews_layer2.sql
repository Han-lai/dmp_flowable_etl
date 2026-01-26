-- ========================================
-- Silver 層 Materialized Views - 第二層（業務邏輯層）- 原生表版本
-- ========================================
-- 用途：基於第一層 MVIEW 計算業務邏輯，產生最終的事實表和維度表
-- 依賴：必須在第一層 MVIEW 建立完成後執行
-- 更新方式：第一層 MVIEW 更新時自動觸發更新
-- 
-- 重要變更：替換 bronze.common_flowable_task_stats 為原生 Flowable 表

-- ========================================
-- 1. 任務 Vx 歸屬事實表 MVIEW - 原生表版本
-- ========================================
-- 基於現有的 FACT_TASK_VX_ATTRIBUTION 邏輯建立 MVIEW 版本
-- 與現有表並行存在，不影響現有流程

DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution;

CREATE MATERIALIZED VIEW silver.mv_fact_task_vx_attribution
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (task_id)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT
    -- 主鍵
    t.ID_ AS task_id,
    
    -- 時間維度
    COALESCE(toDate(t.START_TIME_), toDate('1970-01-01')) AS task_create_date,
    toDateOrNull(t.END_TIME_) AS task_end_date,
    t.START_TIME_ AS task_create_time,
    t.CLAIM_TIME_ AS task_claim_time,
    t.END_TIME_ AS task_end_time,
    
    -- 任務屬性
    COALESCE(
        CASE 
            WHEN t.END_TIME_ IS NOT NULL THEN 'DONE'
            WHEN t.ASSIGNEE_ IS NOT NULL AND t.ASSIGNEE_ != '' THEN 'DOING' 
            ELSE 'TODO'
        END, 
        'Unknown'
    ) AS task_status,
    
    COALESCE(
        CASE WHEN tb.LONG_ = 1 THEN 'Y' ELSE 'N' END, 
        'N'
    ) AS task_bypass,
    
    t.TASK_DEF_KEY_ AS task_definition_key,
    t.NAME_ AS task_name,
    
    -- 人員資訊
    he.EmpName AS task_assignee_name,
    t.ASSIGNEE_ AS task_assignee_account,
    
    -- 預計算：Vx 歸屬（修正後的邏輯：工單號規則優先級最高）
    CASE 
        -- 優先級 1：工單號規則（最高，覆蓋所有 TaskDefinitionKey）
        WHEN COALESCE(v.varinst_moNumber, '') LIKE '196%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '315%'
        THEN 'V1'
        
        -- 優先級 2：TaskDefinitionKey 前綴（當工單號規則不符合時）
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
        WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
        
        -- 預設值
        ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
    END AS vx_type,
    
    -- 預計算：V1 子類型（修正後的邏輯：工單號規則優先，NPE 判別使用 varinst_name 欄位）
    -- varinst_name 是 ACT_HI_VARINST 中所有 NAME_ 值的連接字符串，用於判斷是否包含 NPE 相關變數
    CASE 
        -- 工單號規則的 V1 任務（無論原始 TaskDefinitionKey 是什麼）
        WHEN (COALESCE(v.varinst_moNumber, '') LIKE '196%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '315%')
             AND v.varinst_name LIKE '%NPE%'
        THEN 'V1_NPE'
        
        WHEN (COALESCE(v.varinst_moNumber, '') LIKE '196%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '315%')
        THEN 'V1_MFG'
        
        -- TaskDefinitionKey 的 V1 任務（工單號規則不符合時）
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' AND v.varinst_name LIKE '%NPE%'
        THEN 'V1_NPE'
        
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%'
        THEN 'V1_MFG'
        
        -- 其他情況（V2/V3 等）
        ELSE NULL
    END AS vx_subtype,
    
    -- 是否套用特殊 V1 規則（修正後的邏輯：工單號規則優先）
    CASE 
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 1
        -- 工單號規則（196/199/200/210/212/213/315 開頭）
        WHEN COALESCE(v.varinst_moNumber, '') LIKE '196%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '315%'
        THEN 1
        ELSE 0
    END AS is_special_v1_rule,
    
    -- 排除標記
    CASE 
        WHEN COALESCE(CASE WHEN tb.LONG_ = 1 THEN 'Y' ELSE 'N' END, 'N') != 'N' THEN 1
        WHEN t.TASK_DEF_KEY_ LIKE 'E%' OR t.TASK_DEF_KEY_ LIKE 'C%' THEN 1
        WHEN COALESCE(v.varinst_moNumber, '') LIKE 'Q%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE 'R%' THEN 1
        ELSE 0
    END AS is_excluded,
    
    -- 排除原因
    CASE 
        WHEN COALESCE(CASE WHEN tb.LONG_ = 1 THEN 'Y' ELSE 'N' END, 'N') != 'N' THEN 'bypass'
        WHEN t.TASK_DEF_KEY_ LIKE 'E%' THEN 'E_prefix'
        WHEN t.TASK_DEF_KEY_ LIKE 'C%' THEN 'C_prefix'
        WHEN COALESCE(v.varinst_moNumber, '') LIKE 'Q%' THEN 'Q_order'
        WHEN COALESCE(v.varinst_moNumber, '') LIKE 'R%' THEN 'R_order'
        ELSE NULL
    END AS exclude_reason,
    
    -- 維度
    COALESCE(v.varinst_plant, '') AS plant,
    COALESCE(v.varinst_factory, '') AS factory,
    COALESCE(v.varinst_lineName, '') AS line,
    
    -- 關聯欄位
    t.PROC_INST_ID_ AS proc_inst_id,
    p.BUSINESS_KEY_ AS business_key,
    COALESCE(v.varinst_moNumber, '') AS mo_number,
    p.NAME_ AS proc_name,
    
    -- Metadata
    now64(3) AS _mview_update_time

FROM bronze.bpm_act_hi_taskinst t
LEFT JOIN bronze.bpm_act_hi_procinst p 
    ON t.PROC_INST_ID_ = p.PROC_INST_ID_
LEFT JOIN silver.mv_varinst_pivoted v
    ON t.PROC_INST_ID_ = v.PROC_INST_ID_
LEFT JOIN bronze.common_hr_employee he
    ON t.ASSIGNEE_ = he.EmpCode
-- TaskBypass 來自任務層級變數 autoComplete
LEFT JOIN bronze.bpm_act_hi_varinst tb
    ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
WHERE t.ID_ IS NOT NULL 
  AND t.ID_ != '';

-- ========================================
-- 2. 用戶配置維度表 MVIEW
-- ========================================
-- 基於現有的 DIM_CONFIG_USER 邏輯建立 MVIEW 版本

DROP TABLE IF EXISTS silver.mv_dim_config_user;

CREATE MATERIALIZED VIEW silver.mv_dim_config_user
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (emp_code, vx_type)
POPULATE
AS
WITH 
-- 組合所有員工資料
combined AS (
    SELECT 
        eo.EmpCode AS emp_code,
        ei.EmpName AS emp_name,
        eo.Plant AS plant,
        eo.factory_code AS factory,
        COALESCE(eg.user_group_names, []) AS user_group_names,
        COALESCE(en.node_codes, []) AS node_codes,
        COALESCE(eg.has_whitelist_group, 0) AS has_whitelist_group,
        COALESCE(eg.has_exclude_group, 0) AS has_exclude_group,
        COALESCE(en.has_v1_node, 0) AS has_v1_node,
        COALESCE(en.has_v2_node, 0) AS has_v2_node,
        COALESCE(en.has_v3_node, 0) AS has_v3_node,
        COALESCE(eo.is_npe_factory, 0) AS is_npe_factory,
        COALESCE(eg.user_group_count, 0) AS user_group_count
    FROM silver.mv_emp_org_info eo
    LEFT JOIN silver.mv_emp_user_groups eg ON eo.EmpCode = eg.EmpCode
    LEFT JOIN silver.mv_emp_node_codes en ON eo.EmpCode = en.EmpCode
    LEFT JOIN bronze.common_hr_employee ei ON eo.EmpCode = ei.EmpCode
),

-- 展開 Vx 類型（包含 V3 → V1 特殊規則）
vx_expanded AS (
    SELECT 
        emp_code,
        emp_name,
        plant,
        factory,
        user_group_names,
        node_codes,
        has_whitelist_group,
        has_exclude_group,
        user_group_count,
        
        -- Vx 類型展開（包含 V3 NPE → V1 特殊規則）
        arrayJoin(
            arrayFilter(x -> x != '', 
                arrayDistinct(
                    arrayFlatten([
                        -- V1 規則
                        if(has_v1_node = 1, ['V1'], []),
                        -- V2 規則
                        if(has_v2_node = 1, ['V2'], []),
                        -- V3 規則（NPE 歸 V1，非 NPE 歸 V3）
                        if(has_v3_node = 1 AND is_npe_factory = 1, ['V1'], []),
                        if(has_v3_node = 1 AND is_npe_factory = 0, ['V3'], [])
                    ])
                )
            )
        ) AS vx_type
        
    FROM combined
    WHERE emp_code IS NOT NULL AND emp_code != ''
)

SELECT 
    emp_code,
    vx_type,
    COALESCE(plant, '') AS plant,
    COALESCE(factory, '') AS factory,
    emp_name,
    
    -- 預計算：成員資格
    CASE 
        -- 排除優先
        WHEN has_exclude_group = 1 THEN 0
        -- V1 白名單 (User, PMUser, PowerUser)
        WHEN vx_type = 'V1' AND has_whitelist_group = 1 THEN 1
        -- V2/V3 只允許 User 且無其他身分
        WHEN vx_type IN ('V2', 'V3') AND user_group_count = 1 AND has(user_group_names, 'User') THEN 1
        ELSE 0
    END AS is_config_user,
    
    -- 是否被排除
    CASE 
        WHEN has_exclude_group = 1 THEN 1
        ELSE 0
    END AS is_excluded,
    
    -- 排除原因
    CASE 
        WHEN has(user_group_names, 'ManagerUser') THEN 'ManagerUser'
        WHEN has(user_group_names, 'LocalAdmin') THEN 'LocalAdmin'
        WHEN has(user_group_names, 'GlobalAdmin') THEN 'GlobalAdmin'
        WHEN has(user_group_names, 'SystemAdmin') THEN 'SystemAdmin'
        WHEN has(user_group_names, 'InternalAudit') THEN 'InternalAudit'
        WHEN has(user_group_names, 'SeniorOfficers&DTO') THEN 'SeniorOfficers&DTO'
        ELSE NULL
    END AS exclude_reason,
    
    user_group_names,
    has_whitelist_group,
    has_exclude_group,
    node_codes,
    
    now64(3) AS _mview_update_time

FROM vx_expanded;

-- ========================================
-- 3. L5 指標聚合 MVIEW（原生表版本）
-- ========================================
-- 預聚合 L5 指標，提供即時查詢能力

DROP TABLE IF EXISTS silver.mv_l5_metrics_realtime;

CREATE MATERIALIZED VIEW silver.mv_l5_metrics_realtime
ENGINE = SummingMergeTree()
ORDER BY (snapshot_date, vx_type, vx_subtype, plant, factory, line)
SETTINGS allow_nullable_key = 1
POPULATE
AS
SELECT
    -- 修正日期邏輯：使用與 MSSQL 一致的 OR 邏輯
    CASE 
        WHEN task_create_time IS NOT NULL THEN toDate(task_create_time)
        WHEN task_claim_time IS NOT NULL THEN toDate(task_claim_time)  
        WHEN task_end_time IS NOT NULL THEN toDate(task_end_time)
        ELSE toDate('1970-01-01')
    END AS snapshot_date,
    vx_type,
    vx_subtype,
    plant,
    factory,
    line,
    
    -- 基礎統計（只計算未排除的任務）
    countIf(is_excluded = 0) AS total_task_qty,
    countIf(is_excluded = 0 AND task_status = 'TODO') AS todo_qty,
    countIf(is_excluded = 0 AND task_status = 'DOING') AS doing_qty,
    countIf(is_excluded = 0 AND task_status = 'DONE') AS done_qty,
    
    -- 排除統計
    countIf(is_excluded = 1) AS excluded_qty,
    countIf(exclude_reason = 'bypass') AS bypass_qty,
    countIf(exclude_reason = 'E_prefix') AS e_prefix_qty,
    countIf(exclude_reason = 'C_prefix') AS c_prefix_qty,
    countIf(exclude_reason = 'Q_order') AS q_order_qty,
    countIf(exclude_reason = 'R_order') AS r_order_qty,
    
    -- V1 特殊規則統計
    countIf(is_special_v1_rule = 1) AS special_v1_rule_qty,
    
    now64(3) AS _mview_update_time
    
FROM silver.mv_fact_task_vx_attribution
GROUP BY 
    snapshot_date,
    vx_type,
    vx_subtype,
    plant,
    factory,
    line;

-- ========================================
-- 建立查詢視圖（與現有表格式相容）
-- ========================================
-- 提供與現有 FACT_TASK_VX_ATTRIBUTION 相同介面的查詢視圖

DROP VIEW IF EXISTS silver.vw_fact_task_vx_attribution_realtime;

CREATE VIEW silver.vw_fact_task_vx_attribution_realtime AS
SELECT 
    task_id,
    task_create_date,
    task_end_date,
    task_create_time,
    task_claim_time,
    task_end_time,
    task_status,
    task_bypass,
    task_definition_key,
    task_name,
    task_assignee_name,
    task_assignee_account,
    vx_type,
    vx_subtype,
    is_special_v1_rule,
    is_excluded,
    exclude_reason,
    plant,
    factory,
    line,
    proc_inst_id,
    business_key,
    mo_number,
    proc_name,
    _mview_update_time AS _transform_time
FROM silver.mv_fact_task_vx_attribution FINAL;

-- ========================================
-- 建立完成提示
-- ========================================
SELECT 'Silver Layer 2 Native MViews Created Successfully' AS status,
       'MVIEW tables: mv_fact_task_vx_attribution, mv_dim_config_user, mv_l5_metrics_realtime' AS created_tables,
       'Query view: vw_fact_task_vx_attribution_realtime' AS created_views;