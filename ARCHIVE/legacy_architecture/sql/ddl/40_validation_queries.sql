-- ========================================
-- 驗收查詢 - 驗證維度補齊邏輯
-- ========================================

-- ========================================
-- 1. 驗證非 V1 流程的維度補齊邏輯
-- ========================================

-- 使用 6 個非 V1 proc_inst_id 驗證
WITH test_proc_ids AS (
    SELECT proc_inst_id FROM (
        VALUES 
        ('38cfc17e-ef5a-11f0-a787-0a5a5063cfa7'),
        ('761d901080ab-11f0-a787-0a5a5063cfa7'),
        ('b6733f7db4dd-11f0-a787-0a5a5063cfa7'),
        ('92564f99f227-11f0-a787-0a5a5063cfa7'),
        ('1e564a6128f7-11f0-a787-0a5a5063cfa7'),
        ('0a5a5063cfa7-11f0-a787-0a5a5063cfa7')
    ) AS t(proc_inst_id)
),

validation_data AS (
    SELECT 
        s.proc_inst_id,
        s.vx_type,
        
        -- 檢查維度值和來源
        s.region,
        s.region_source,
        s.plant,
        s.plant_source,
        s.factory,
        s.factory_source,
        s.line,
        s.line_source,
        
        -- 檢查 VARINST 原始值（從透視表）
        v.varinst_region,
        v.varinst_plant,
        v.varinst_factory,
        v.varinst_lineName,
        
        -- 檢查 MDM 值（透過 line 串接）
        m.region_code AS mdm_region,
        m.plant_code AS mdm_plant,
        m.factory_code AS mdm_factory,
        m.line_name AS mdm_line
        
    FROM silver.mv_fact_task_vx_attribution_mdm s
    INNER JOIN test_proc_ids t ON s.proc_inst_id = t.proc_inst_id
    LEFT JOIN silver.mv_varinst_pivoted v ON s.proc_inst_id = v.PROC_INST_ID_
    LEFT JOIN silver.dim_mfg_five_level m ON v.varinst_lineName = m.line_name
    WHERE s.vx_type != 'V1'  -- 非 V1 流程
    LIMIT 1 BY s.proc_inst_id  -- 每個流程只取一筆
)

SELECT 
    '=== 維度補齊邏輯驗收結果 ===' AS validation_title,
    proc_inst_id,
    vx_type,
    
    -- Region 驗證
    CASE 
        WHEN varinst_region IS NULL OR varinst_region = '' THEN
            CASE 
                WHEN region_source = 'MDM' AND region = mdm_region THEN '✅ Region MDM 補齊正確'
                ELSE '❌ Region MDM 補齊失敗'
            END
        ELSE
            CASE 
                WHEN region_source = 'VARINST' AND region = varinst_region THEN '✅ Region VARINST 優先正確'
                ELSE '❌ Region VARINST 優先失敗'
            END
    END AS region_validation,
    
    -- Plant 驗證
    CASE 
        WHEN varinst_plant IS NULL OR varinst_plant = '' THEN
            CASE 
                WHEN plant_source = 'MDM' AND plant = mdm_plant THEN '✅ Plant MDM 補齊正確'
                WHEN plant_source = 'MISSING' THEN '⚠️ Plant 無資料'
                ELSE '❌ Plant MDM 補齊失敗'
            END
        ELSE
            CASE 
                WHEN plant_source = 'VARINST' AND plant = varinst_plant THEN '✅ Plant VARINST 優先正確'
                ELSE '❌ Plant VARINST 優先失敗'
            END
    END AS plant_validation,
    
    -- Factory 驗證
    CASE 
        WHEN varinst_factory IS NULL OR varinst_factory = '' THEN
            CASE 
                WHEN factory_source = 'MDM' AND factory = mdm_factory THEN '✅ Factory MDM 補齊正確'
                WHEN factory_source = 'MISSING' THEN '⚠️ Factory 無資料'
                ELSE '❌ Factory MDM 補齊失敗'
            END
        ELSE
            CASE 
                WHEN factory_source = 'VARINST' AND factory = varinst_factory THEN '✅ Factory VARINST 優先正確'
                ELSE '❌ Factory VARINST 優先失敗'
            END
    END AS factory_validation,
    
    -- Line 驗證
    CASE 
        WHEN varinst_lineName IS NULL OR varinst_lineName = '' THEN
            CASE 
                WHEN line_source = 'MDM' AND line = mdm_line THEN '✅ Line MDM 補齊正確'
                WHEN line_source = 'MISSING' THEN '⚠️ Line 無資料'
                ELSE '❌ Line MDM 補齊失敗'
            END
        ELSE
            CASE 
                WHEN line_source = 'VARINST' AND line = varinst_lineName THEN '✅ Line VARINST 優先正確'
                ELSE '❌ Line VARINST 優先失敗'
            END
    END AS line_validation,
    
    -- 詳細資料
    concat('VARINST: ', varinst_region, '|', varinst_plant, '|', varinst_factory, '|', varinst_lineName) AS varinst_values,
    concat('MDM: ', mdm_region, '|', mdm_plant, '|', mdm_factory, '|', mdm_line) AS mdm_values,
    concat('FINAL: ', region, '|', plant, '|', factory, '|', line) AS final_values,
    concat('SOURCE: ', region_source, '|', plant_source, '|', factory_source, '|', line_source) AS source_values

FROM validation_data
ORDER BY proc_inst_id;

-- ========================================
-- 2. 統計驗證
-- ========================================

SELECT 
    '=== 維度補齊統計驗證 ===' AS validation_title,
    COUNT(*) AS total_records,
    
    -- Region 統計
    SUM(CASE WHEN region != '' THEN 1 ELSE 0 END) AS has_region,
    SUM(CASE WHEN region_source = 'VARINST' THEN 1 ELSE 0 END) AS region_from_varinst,
    SUM(CASE WHEN region_source = 'MDM' THEN 1 ELSE 0 END) AS region_from_mdm,
    
    -- Plant 統計
    SUM(CASE WHEN plant != '' THEN 1 ELSE 0 END) AS has_plant,
    SUM(CASE WHEN plant_source = 'VARINST' THEN 1 ELSE 0 END) AS plant_from_varinst,
    SUM(CASE WHEN plant_source = 'MDM' THEN 1 ELSE 0 END) AS plant_from_mdm,
    
    -- Factory 統計
    SUM(CASE WHEN factory != '' THEN 1 ELSE 0 END) AS has_factory,
    SUM(CASE WHEN factory_source = 'VARINST' THEN 1 ELSE 0 END) AS factory_from_varinst,
    SUM(CASE WHEN factory_source = 'MDM' THEN 1 ELSE 0 END) AS factory_from_mdm,
    
    -- Line 統計
    SUM(CASE WHEN line != '' THEN 1 ELSE 0 END) AS has_line,
    SUM(CASE WHEN line_source = 'VARINST' THEN 1 ELSE 0 END) AS line_from_varinst,
    SUM(CASE WHEN line_source = 'MDM' THEN 1 ELSE 0 END) AS line_from_mdm

FROM silver.mv_fact_task_vx_attribution_mdm
WHERE task_create_date >= '2025-12-01'
  AND vx_type != 'V1';

-- ========================================
-- 3. Gold 層資料驗證
-- ========================================

SELECT 
    '=== Gold 層資料驗證 ===' AS validation_title,
    COUNT(*) AS total_records,
    COUNT(DISTINCT snapshot_date) AS date_count,
    COUNT(DISTINCT vx_type) AS vx_type_count,
    COUNT(DISTINCT region) AS region_count,
    COUNT(DISTINCT plant) AS plant_count,
    COUNT(DISTINCT factory) AS factory_count,
    SUM(total_task) AS total_tasks,
    SUM(region_mdm_backfill_count) AS total_region_mdm_backfill

FROM gold.l5_dashboard_summary;

SELECT 'Validation queries completed successfully' AS status;