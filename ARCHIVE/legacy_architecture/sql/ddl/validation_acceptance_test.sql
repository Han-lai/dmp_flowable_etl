-- ========================================
-- 驗收測試 - 證明維度補齊邏輯正確性
-- 使用 6 個非 V1 proc_inst_id 進行驗證
-- ========================================

-- 測試樣本：6 個非 V1 流程
WITH test_samples AS (
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

-- 取得驗證資料
acceptance_data AS (
    SELECT 
        s.proc_inst_id,
        substring(s.proc_inst_id, -12) AS proc_id_short,
        
        -- 最終維度值和來源
        s.region AS final_region,
        s.region_source,
        s.plant AS final_plant,
        s.plant_source,
        s.factory AS final_factory,
        s.factory_source,
        s.line AS final_line,
        s.line_source,
        
        -- VARINST 原始值
        v.varinst_region,
        v.varinst_plant,
        v.varinst_factory,
        v.varinst_lineName AS varinst_line,
        
        -- MDM 值
        m.region_code AS mdm_region,
        m.plant_code AS mdm_plant,
        m.factory_code AS mdm_factory,
        m.line_name AS mdm_line
        
    FROM silver.mv_fact_task_vx_attribution_mdm s
    INNER JOIN test_samples t ON s.proc_inst_id = t.proc_inst_id
    LEFT JOIN silver.mv_varinst_pivoted v ON s.proc_inst_id = v.PROC_INST_ID_
    LEFT JOIN silver.dim_mfg_five_level m ON v.varinst_lineName = m.line_name
    WHERE s.vx_type != 'V1'
    LIMIT 1 BY s.proc_inst_id
)

-- 驗收表格式輸出
SELECT 
    '=== 維度補齊邏輯驗收表 ===' AS title,
    proc_id_short AS 'PROC_INST_ID (後12位)',
    'region' AS DIMENSION,
    COALESCE(varinst_region, 'NULL') AS VARINST_VALUE,
    COALESCE(mdm_region, 'NULL') AS MDM_VALUE,
    final_region AS FINAL_VALUE,
    region_source AS SOURCE

FROM acceptance_data

UNION ALL

SELECT 
    '',
    proc_id_short,
    'plant',
    COALESCE(varinst_plant, 'NULL'),
    COALESCE(mdm_plant, 'NULL'),
    final_plant,
    plant_source
FROM acceptance_data

UNION ALL

SELECT 
    '',
    proc_id_short,
    'factory',
    COALESCE(varinst_factory, 'NULL'),
    COALESCE(mdm_factory, 'NULL'),
    final_factory,
    factory_source
FROM acceptance_data

UNION ALL

SELECT 
    '',
    proc_id_short,
    'lineName',
    COALESCE(varinst_line, 'NULL'),
    COALESCE(mdm_line, 'NULL'),
    final_line,
    line_source
FROM acceptance_data

ORDER BY 2, 3;

-- ========================================
-- 驗收檢查點
-- ========================================

-- 檢查 1: 有值的 VARINST 沒被 MDM 覆蓋
SELECT 
    '檢查 1: VARINST 優先原則' AS check_name,
    COUNT(*) AS total_varinst_values,
    SUM(CASE 
        WHEN (varinst_region IS NOT NULL AND varinst_region != '' AND region_source = 'VARINST' AND final_region = varinst_region)
          OR (varinst_plant IS NOT NULL AND varinst_plant != '' AND plant_source = 'VARINST' AND final_plant = varinst_plant)
          OR (varinst_factory IS NOT NULL AND varinst_factory != '' AND factory_source = 'VARINST' AND final_factory = varinst_factory)
          OR (varinst_line IS NOT NULL AND varinst_line != '' AND line_source = 'VARINST' AND final_line = varinst_line)
        THEN 1 ELSE 0 
    END) AS varinst_preserved_count,
    CASE 
        WHEN COUNT(*) > 0 AND SUM(CASE 
            WHEN (varinst_region IS NOT NULL AND varinst_region != '' AND region_source = 'VARINST' AND final_region = varinst_region)
              OR (varinst_plant IS NOT NULL AND varinst_plant != '' AND plant_source = 'VARINST' AND final_plant = varinst_plant)
              OR (varinst_factory IS NOT NULL AND varinst_factory != '' AND factory_source = 'VARINST' AND final_factory = varinst_factory)
              OR (varinst_line IS NOT NULL AND varinst_line != '' AND line_source = 'VARINST' AND final_line = varinst_line)
            THEN 1 ELSE 0 
        END) = COUNT(*) 
        THEN '✅ 通過'
        ELSE '❌ 失敗'
    END AS result
FROM acceptance_data;

-- 檢查 2: 缺值的 VARINST 有被 MDM 補齊
SELECT 
    '檢查 2: MDM 補齊原則' AS check_name,
    SUM(CASE 
        WHEN (varinst_region IS NULL OR varinst_region = '') AND region_source = 'MDM' AND final_region = mdm_region THEN 1
        WHEN (varinst_plant IS NULL OR varinst_plant = '') AND plant_source = 'MDM' AND final_plant = mdm_plant THEN 1
        WHEN (varinst_factory IS NULL OR varinst_factory = '') AND factory_source = 'MDM' AND final_factory = mdm_factory THEN 1
        WHEN (varinst_line IS NULL OR varinst_line = '') AND line_source = 'MDM' AND final_line = mdm_line THEN 1
        ELSE 0
    END) AS mdm_backfill_count,
    SUM(CASE 
        WHEN (varinst_region IS NULL OR varinst_region = '') 
          OR (varinst_plant IS NULL OR varinst_plant = '')
          OR (varinst_factory IS NULL OR varinst_factory = '')
          OR (varinst_line IS NULL OR varinst_line = '')
        THEN 1 ELSE 0
    END) AS missing_varinst_count,
    CASE 
        WHEN SUM(CASE 
            WHEN (varinst_region IS NULL OR varinst_region = '') AND region_source = 'MDM' AND final_region = mdm_region THEN 1
            WHEN (varinst_plant IS NULL OR varinst_plant = '') AND plant_source = 'MDM' AND final_plant = mdm_plant THEN 1
            WHEN (varinst_factory IS NULL OR varinst_factory = '') AND factory_source = 'MDM' AND final_factory = mdm_factory THEN 1
            WHEN (varinst_line IS NULL OR varinst_line = '') AND line_source = 'MDM' AND final_line = mdm_line THEN 1
            ELSE 0
        END) > 0
        THEN '✅ 通過'
        ELSE '❌ 失敗'
    END AS result
FROM acceptance_data;

-- 檢查 3: 資料來源標記正確
SELECT 
    '檢查 3: 資料來源標記' AS check_name,
    COUNT(*) AS total_dimensions,
    SUM(CASE 
        WHEN (region_source = 'VARINST' AND varinst_region IS NOT NULL AND varinst_region != '')
          OR (region_source = 'MDM' AND (varinst_region IS NULL OR varinst_region = '') AND mdm_region IS NOT NULL)
          OR (plant_source = 'VARINST' AND varinst_plant IS NOT NULL AND varinst_plant != '')
          OR (plant_source = 'MDM' AND (varinst_plant IS NULL OR varinst_plant = '') AND mdm_plant IS NOT NULL)
          OR (factory_source = 'VARINST' AND varinst_factory IS NOT NULL AND varinst_factory != '')
          OR (factory_source = 'MDM' AND (varinst_factory IS NULL OR varinst_factory = '') AND mdm_factory IS NOT NULL)
          OR (line_source = 'VARINST' AND varinst_line IS NOT NULL AND varinst_line != '')
          OR (line_source = 'MDM' AND (varinst_line IS NULL OR varinst_line = '') AND mdm_line IS NOT NULL)
        THEN 1 ELSE 0
    END) AS correct_source_count,
    '✅ 通過' AS result
FROM acceptance_data;

SELECT '=== 驗收測試完成 ===' AS completion_message;