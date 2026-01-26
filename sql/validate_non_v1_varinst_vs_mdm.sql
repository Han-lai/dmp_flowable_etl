-- ========================================
-- 非 V1 流程 VARINST vs MDM 缺口分析驗證 SQL
-- ========================================
-- 目標：證明非 V1 流程在 VARINST 中無法取得完整五階維度，必須依賴 MDM 補齊
-- 指定驗證樣本：6 個非 V1 流程的 PROC_INST_ID_

-- ========================================
-- 1. VARINST 缺失驗證
-- ========================================
SELECT '1. VARINST 缺失驗證' AS section;

-- 1.1 檢查指定 PROC_INST_ID_ 在 VARINST 中的實際內容
WITH target_proc_inst AS (
    SELECT arrayJoin([
        '3c40f619-c593-11f0-8d58-1e564a6128f7',
        '38cfc17e-ef5a-11f0-a787-0a5a5063cfa7', 
        '3ca530c5-d938-11f0-8eb2-761d901080ab',
        '505b457d-63b3-11f0-b8b8-b6733f7db4dd',
        '3c60482b-ecf9-11f0-ba59-92564f99f227',
        '3ca93700-ef50-11f0-a787-0a5a5063cfa7'
    ]) AS proc_inst_id
),
varinst_actual AS (
    SELECT 
        v.PROC_INST_ID_,
        v.NAME_,
        v.TEXT_,
        v.LONG_,
        v.DOUBLE_
    FROM bronze.bpm_act_hi_varinst AS v
    INNER JOIN target_proc_inst AS t ON v.PROC_INST_ID_ = t.proc_inst_id
    WHERE v.NAME_ IS NOT NULL AND v.NAME_ != ''
)

SELECT 
    PROC_INST_ID_,
    NAME_,
    TEXT_,
    CASE WHEN TEXT_ IS NULL OR TEXT_ = '' THEN '❌ 空值' ELSE '✅ 有值' END AS has_value
FROM varinst_actual
ORDER BY PROC_INST_ID_, NAME_;

-- 1.2 彙總每個 PROC_INST_ID_ 的維度缺失情況
WITH target_proc_inst AS (
    SELECT arrayJoin([
        '3c40f619-c593-11f0-8d58-1e564a6128f7',
        '38cfc17e-ef5a-11f0-a787-0a5a5063cfa7', 
        '3ca530c5-d938-11f0-8eb2-761d901080ab',
        '505b457d-63b3-11f0-b8b8-b6733f7db4dd',
        '3c60482b-ecf9-11f0-ba59-92564f99f227',
        '3ca93700-ef50-11f0-a787-0a5a5063cfa7'
    ]) AS proc_inst_id
),
dimension_check AS (
    SELECT 
        t.proc_inst_id,
        
        -- 檢查 region 維度
        CASE 
            WHEN EXISTS(
                SELECT 1 FROM bronze.bpm_act_hi_varinst v 
                WHERE v.PROC_INST_ID_ = t.proc_inst_id 
                  AND v.NAME_ = 'region' 
                  AND v.TEXT_ IS NOT NULL 
                  AND v.TEXT_ != ''
            ) THEN '✅ 存在' 
            ELSE '❌ 缺失' 
        END AS region_status,
        
        -- 檢查 plant 維度
        CASE 
            WHEN EXISTS(
                SELECT 1 FROM bronze.bpm_act_hi_varinst v 
                WHERE v.PROC_INST_ID_ = t.proc_inst_id 
                  AND v.NAME_ = 'plant' 
                  AND v.TEXT_ IS NOT NULL 
                  AND v.TEXT_ != ''
            ) THEN '✅ 存在' 
            ELSE '❌ 缺失' 
        END AS plant_status,
        
        -- 檢查 factory 維度
        CASE 
            WHEN EXISTS(
                SELECT 1 FROM bronze.bpm_act_hi_varinst v 
                WHERE v.PROC_INST_ID_ = t.proc_inst_id 
                  AND v.NAME_ = 'factory' 
                  AND v.TEXT_ IS NOT NULL 
                  AND v.TEXT_ != ''
            ) THEN '✅ 存在' 
            ELSE '❌ 缺失' 
        END AS factory_status,
        
        -- 檢查 lineName 維度
        CASE 
            WHEN EXISTS(
                SELECT 1 FROM bronze.bpm_act_hi_varinst v 
                WHERE v.PROC_INST_ID_ = t.proc_inst_id 
                  AND v.NAME_ = 'lineName' 
                  AND v.TEXT_ IS NOT NULL 
                  AND v.TEXT_ != ''
            ) THEN '✅ 存在' 
            ELSE '❌ 缺失' 
        END AS lineName_status
        
    FROM target_proc_inst AS t
)

SELECT 
    proc_inst_id,
    region_status,
    plant_status,
    factory_status,
    lineName_status,
    
    -- 統計缺失維度數量
    CASE WHEN region_status = '❌ 缺失' THEN 1 ELSE 0 END +
    CASE WHEN plant_status = '❌ 缺失' THEN 1 ELSE 0 END +
    CASE WHEN factory_status = '❌ 缺失' THEN 1 ELSE 0 END +
    CASE WHEN lineName_status = '❌ 缺失' THEN 1 ELSE 0 END AS missing_dimensions_count
    
FROM dimension_check
ORDER BY proc_inst_id;

-- ========================================
-- 2. MDM 補齊驗證
-- ========================================
SELECT '2. MDM 補齊驗證' AS section;

-- 2.1 從流程資料找出可用於 MDM join 的 key
WITH target_proc_inst AS (
    SELECT arrayJoin([
        '3c40f619-c593-11f0-8d58-1e564a6128f7',
        '38cfc17e-ef5a-11f0-a787-0a5a5063cfa7', 
        '3ca530c5-d938-11f0-8eb2-761d901080ab',
        '505b457d-63b3-11f0-b8b8-b6733f7db4dd',
        '3c60482b-ecf9-11f0-ba59-92564f99f227',
        '3ca93700-ef50-11f0-a787-0a5a5063cfa7'
    ]) AS proc_inst_id
),
proc_info AS (
    SELECT 
        p.PROC_INST_ID_,
        p.BUSINESS_KEY_,
        p.NAME_ AS proc_name,
        
        -- 從 BUSINESS_KEY_ 解析可能的維度資訊
        multiIf(
            p.BUSINESS_KEY_ LIKE '%"plant":"%', 
            extract(p.BUSINESS_KEY_, '"plant":"([^"]+)"'),
            ''
        ) AS business_key_plant,
        
        multiIf(
            p.BUSINESS_KEY_ LIKE '%"factory":"%', 
            extract(p.BUSINESS_KEY_, '"factory":"([^"]+)"'),
            ''
        ) AS business_key_factory,
        
        multiIf(
            p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
            extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'),
            ''
        ) AS business_key_line
        
    FROM bronze.bpm_act_hi_procinst AS p
    INNER JOIN target_proc_inst AS t ON p.PROC_INST_ID_ = t.proc_inst_id
),
-- 嘗試從任務表取得額外的 join key
task_info AS (
    SELECT 
        task.PROC_INST_ID_,
        task.TASK_DEF_KEY_,
        task.NAME_ AS task_name,
        
        -- 檢查 task definition key 是否包含維度資訊
        CASE 
            WHEN task.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
            WHEN task.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
            ELSE 'OTHER'
        END AS vx_type
        
    FROM bronze.bpm_act_hi_taskinst AS task
    INNER JOIN target_proc_inst AS t ON task.PROC_INST_ID_ = t.proc_inst_id
    GROUP BY task.PROC_INST_ID_, task.TASK_DEF_KEY_, task.NAME_, vx_type
)

SELECT 
    p.PROC_INST_ID_,
    p.proc_name,
    p.BUSINESS_KEY_,
    p.business_key_plant,
    p.business_key_factory,
    p.business_key_line,
    t.vx_type,
    
    -- 標記可用於 MDM join 的 key
    CASE 
        WHEN p.business_key_line != '' THEN p.business_key_line
        ELSE '❌ 無可用 line key'
    END AS available_join_key
    
FROM proc_info AS p
LEFT JOIN task_info AS t ON p.PROC_INST_ID_ = t.PROC_INST_ID_
ORDER BY p.PROC_INST_ID_;

-- 2.2 使用 MDM 表補齊五階維度
WITH target_proc_inst AS (
    SELECT arrayJoin([
        '3c40f619-c593-11f0-8d58-1e564a6128f7',
        '38cfc17e-ef5a-11f0-a787-0a5a5063cfa7', 
        '3ca530c5-d938-11f0-8eb2-761d901080ab',
        '505b457d-63b3-11f0-b8b8-b6733f7db4dd',
        '3c60482b-ecf9-11f0-ba59-92564f99f227',
        '3ca93700-ef50-11f0-a787-0a5a5063cfa7'
    ]) AS proc_inst_id
),
proc_with_keys AS (
    SELECT 
        p.PROC_INST_ID_,
        
        -- 從 BUSINESS_KEY_ 解析 line key
        multiIf(
            p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
            extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'),
            ''
        ) AS business_key_line
        
    FROM bronze.bpm_act_hi_procinst AS p
    INNER JOIN target_proc_inst AS t ON p.PROC_INST_ID_ = t.proc_inst_id
),
mdm_mapping AS (
    SELECT 
        pk.PROC_INST_ID_,
        pk.business_key_line,
        
        -- 從 MDM 表補齊五階維度
        mdm.region_code AS mdm_region,
        mdm.plant_code AS mdm_plant,
        mdm.factory_code AS mdm_factory,
        mdm.line_name AS mdm_line,
        
        -- 標記 MDM join 是否成功
        CASE 
            WHEN mdm.line_name IS NOT NULL THEN '✅ MDM 成功'
            ELSE '❌ MDM 失敗'
        END AS mdm_join_status
        
    FROM proc_with_keys AS pk
    LEFT JOIN silver.dim_mfg_five_level AS mdm ON pk.business_key_line = mdm.line_name
)

SELECT 
    PROC_INST_ID_,
    business_key_line,
    mdm_join_status,
    mdm_region,
    mdm_plant,
    mdm_factory,
    mdm_line
FROM mdm_mapping
ORDER BY PROC_INST_ID_;

-- ========================================
-- 3. 對照輸出驗證（VARINST vs MDM）
-- ========================================
SELECT '3. 對照輸出驗證' AS section;

WITH target_proc_inst AS (
    SELECT arrayJoin([
        '3c40f619-c593-11f0-8d58-1e564a6128f7',
        '38cfc17e-ef5a-11f0-a787-0a5a5063cfa7', 
        '3ca530c5-d938-11f0-8eb2-761d901080ab',
        '505b457d-63b3-11f0-b8b8-b6733f7db4dd',
        '3c60482b-ecf9-11f0-ba59-92564f99f227',
        '3ca93700-ef50-11f0-a787-0a5a5063cfa7'
    ]) AS proc_inst_id
),
-- 取得 VARINST 維度值
varinst_dimensions AS (
    SELECT 
        t.proc_inst_id,
        
        -- 從 VARINST 取得維度值（如果存在）
        (SELECT v.TEXT_ FROM bronze.bpm_act_hi_varinst v 
         WHERE v.PROC_INST_ID_ = t.proc_inst_id AND v.NAME_ = 'region' 
         LIMIT 1) AS varinst_region,
         
        (SELECT v.TEXT_ FROM bronze.bpm_act_hi_varinst v 
         WHERE v.PROC_INST_ID_ = t.proc_inst_id AND v.NAME_ = 'plant' 
         LIMIT 1) AS varinst_plant,
         
        (SELECT v.TEXT_ FROM bronze.bpm_act_hi_varinst v 
         WHERE v.PROC_INST_ID_ = t.proc_inst_id AND v.NAME_ = 'factory' 
         LIMIT 1) AS varinst_factory,
         
        (SELECT v.TEXT_ FROM bronze.bpm_act_hi_varinst v 
         WHERE v.PROC_INST_ID_ = t.proc_inst_id AND v.NAME_ = 'lineName' 
         LIMIT 1) AS varinst_line
         
    FROM target_proc_inst AS t
),
-- 取得 MDM 維度值
mdm_dimensions AS (
    SELECT 
        p.PROC_INST_ID_,
        
        -- 從 BUSINESS_KEY_ 解析 join key
        multiIf(
            p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
            extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'),
            ''
        ) AS join_key,
        
        -- 從 MDM 取得維度值
        mdm.region_code AS mdm_region,
        mdm.plant_code AS mdm_plant,
        mdm.factory_code AS mdm_factory,
        mdm.line_name AS mdm_line
        
    FROM bronze.bpm_act_hi_procinst AS p
    INNER JOIN target_proc_inst AS t ON p.PROC_INST_ID_ = t.proc_inst_id
    LEFT JOIN silver.dim_mfg_five_level AS mdm ON 
        multiIf(
            p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
            extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'),
            ''
        ) = mdm.line_name
)

SELECT 
    v.proc_inst_id,
    
    -- VARINST 維度值
    COALESCE(v.varinst_region, 'NULL') AS varinst_region,
    COALESCE(v.varinst_plant, 'NULL') AS varinst_plant,
    COALESCE(v.varinst_factory, 'NULL') AS varinst_factory,
    COALESCE(v.varinst_line, 'NULL') AS varinst_line,
    
    -- MDM 維度值
    COALESCE(m.mdm_region, 'NULL') AS mdm_region,
    COALESCE(m.mdm_plant, 'NULL') AS mdm_plant,
    COALESCE(m.mdm_factory, 'NULL') AS mdm_factory,
    COALESCE(m.mdm_line, 'NULL') AS mdm_line,
    
    -- 對比結果
    CASE 
        WHEN v.varinst_region IS NULL AND m.mdm_region IS NOT NULL THEN '✅ MDM 補齊'
        WHEN v.varinst_region IS NOT NULL THEN '⚠️ VARINST 有值'
        ELSE '❌ 都無值'
    END AS region_comparison,
    
    CASE 
        WHEN v.varinst_plant IS NULL AND m.mdm_plant IS NOT NULL THEN '✅ MDM 補齊'
        WHEN v.varinst_plant IS NOT NULL THEN '⚠️ VARINST 有值'
        ELSE '❌ 都無值'
    END AS plant_comparison,
    
    CASE 
        WHEN v.varinst_factory IS NULL AND m.mdm_factory IS NOT NULL THEN '✅ MDM 補齊'
        WHEN v.varinst_factory IS NOT NULL THEN '⚠️ VARINST 有值'
        ELSE '❌ 都無值'
    END AS factory_comparison,
    
    CASE 
        WHEN v.varinst_line IS NULL AND m.mdm_line IS NOT NULL THEN '✅ MDM 補齊'
        WHEN v.varinst_line IS NOT NULL THEN '⚠️ VARINST 有值'
        ELSE '❌ 都無值'
    END AS line_comparison
    
FROM varinst_dimensions AS v
LEFT JOIN mdm_dimensions AS m ON v.proc_inst_id = m.PROC_INST_ID_
ORDER BY v.proc_inst_id;

-- ========================================
-- 4. 總結統計
-- ========================================
SELECT '4. 總結統計' AS section;

WITH target_proc_inst AS (
    SELECT arrayJoin([
        '3c40f619-c593-11f0-8d58-1e564a6128f7',
        '38cfc17e-ef5a-11f0-a787-0a5a5063cfa7', 
        '3ca530c5-d938-11f0-8eb2-761d901080ab',
        '505b457d-63b3-11f0-b8b8-b6733f7db4dd',
        '3c60482b-ecf9-11f0-ba59-92564f99f227',
        '3ca93700-ef50-11f0-a787-0a5a5063cfa7'
    ]) AS proc_inst_id
),
summary_stats AS (
    SELECT 
        COUNT(*) AS total_proc_inst,
        
        -- VARINST 維度缺失統計
        SUM(CASE WHEN NOT EXISTS(
            SELECT 1 FROM bronze.bpm_act_hi_varinst v 
            WHERE v.PROC_INST_ID_ = t.proc_inst_id AND v.NAME_ = 'region' 
              AND v.TEXT_ IS NOT NULL AND v.TEXT_ != ''
        ) THEN 1 ELSE 0 END) AS varinst_region_missing,
        
        SUM(CASE WHEN NOT EXISTS(
            SELECT 1 FROM bronze.bpm_act_hi_varinst v 
            WHERE v.PROC_INST_ID_ = t.proc_inst_id AND v.NAME_ = 'plant' 
              AND v.TEXT_ IS NOT NULL AND v.TEXT_ != ''
        ) THEN 1 ELSE 0 END) AS varinst_plant_missing,
        
        SUM(CASE WHEN NOT EXISTS(
            SELECT 1 FROM bronze.bpm_act_hi_varinst v 
            WHERE v.PROC_INST_ID_ = t.proc_inst_id AND v.NAME_ = 'factory' 
              AND v.TEXT_ IS NOT NULL AND v.TEXT_ != ''
        ) THEN 1 ELSE 0 END) AS varinst_factory_missing,
        
        SUM(CASE WHEN NOT EXISTS(
            SELECT 1 FROM bronze.bpm_act_hi_varinst v 
            WHERE v.PROC_INST_ID_ = t.proc_inst_id AND v.NAME_ = 'lineName' 
              AND v.TEXT_ IS NOT NULL AND v.TEXT_ != ''
        ) THEN 1 ELSE 0 END) AS varinst_line_missing,
        
        -- MDM 補齊成功統計
        SUM(CASE WHEN EXISTS(
            SELECT 1 FROM bronze.bpm_act_hi_procinst p
            LEFT JOIN silver.dim_mfg_five_level mdm ON 
                multiIf(p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
                        extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'), '') = mdm.line_name
            WHERE p.PROC_INST_ID_ = t.proc_inst_id AND mdm.region_code IS NOT NULL
        ) THEN 1 ELSE 0 END) AS mdm_region_success,
        
        SUM(CASE WHEN EXISTS(
            SELECT 1 FROM bronze.bpm_act_hi_procinst p
            LEFT JOIN silver.dim_mfg_five_level mdm ON 
                multiIf(p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
                        extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'), '') = mdm.line_name
            WHERE p.PROC_INST_ID_ = t.proc_inst_id AND mdm.plant_code IS NOT NULL
        ) THEN 1 ELSE 0 END) AS mdm_plant_success,
        
        SUM(CASE WHEN EXISTS(
            SELECT 1 FROM bronze.bpm_act_hi_procinst p
            LEFT JOIN silver.dim_mfg_five_level mdm ON 
                multiIf(p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
                        extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'), '') = mdm.line_name
            WHERE p.PROC_INST_ID_ = t.proc_inst_id AND mdm.factory_code IS NOT NULL
        ) THEN 1 ELSE 0 END) AS mdm_factory_success,
        
        SUM(CASE WHEN EXISTS(
            SELECT 1 FROM bronze.bpm_act_hi_procinst p
            LEFT JOIN silver.dim_mfg_five_level mdm ON 
                multiIf(p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
                        extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'), '') = mdm.line_name
            WHERE p.PROC_INST_ID_ = t.proc_inst_id AND mdm.line_name IS NOT NULL
        ) THEN 1 ELSE 0 END) AS mdm_line_success
        
    FROM target_proc_inst AS t
)

SELECT 
    '驗證樣本總數' AS metric,
    total_proc_inst AS value,
    '' AS percentage
FROM summary_stats

UNION ALL

SELECT 
    'VARINST Region 缺失' AS metric,
    varinst_region_missing AS value,
    CONCAT(ROUND(varinst_region_missing * 100.0 / total_proc_inst, 1), '%') AS percentage
FROM summary_stats

UNION ALL

SELECT 
    'VARINST Plant 缺失' AS metric,
    varinst_plant_missing AS value,
    CONCAT(ROUND(varinst_plant_missing * 100.0 / total_proc_inst, 1), '%') AS percentage
FROM summary_stats

UNION ALL

SELECT 
    'VARINST Factory 缺失' AS metric,
    varinst_factory_missing AS value,
    CONCAT(ROUND(varinst_factory_missing * 100.0 / total_proc_inst, 1), '%') AS percentage
FROM summary_stats

UNION ALL

SELECT 
    'VARINST Line 缺失' AS metric,
    varinst_line_missing AS value,
    CONCAT(ROUND(varinst_line_missing * 100.0 / total_proc_inst, 1), '%') AS percentage
FROM summary_stats

UNION ALL

SELECT 
    'MDM Region 補齊成功' AS metric,
    mdm_region_success AS value,
    CONCAT(ROUND(mdm_region_success * 100.0 / total_proc_inst, 1), '%') AS percentage
FROM summary_stats

UNION ALL

SELECT 
    'MDM Plant 補齊成功' AS metric,
    mdm_plant_success AS value,
    CONCAT(ROUND(mdm_plant_success * 100.0 / total_proc_inst, 1), '%') AS percentage
FROM summary_stats

UNION ALL

SELECT 
    'MDM Factory 補齊成功' AS metric,
    mdm_factory_success AS value,
    CONCAT(ROUND(mdm_factory_success * 100.0 / total_proc_inst, 1), '%') AS percentage
FROM summary_stats

UNION ALL

SELECT 
    'MDM Line 補齊成功' AS metric,
    mdm_line_success AS value,
    CONCAT(ROUND(mdm_line_success * 100.0 / total_proc_inst, 1), '%') AS percentage
FROM summary_stats;