-- ========================================
-- 建立 Silver 層製造五階維度表
-- ========================================
-- 目的：基於 MDM 主檔表建立完整的製造五階維度
-- 維度定義：Region → Vx → Plant → Factory → Line
-- 資料來源：MDM 主檔表優先，Flowable 作為 fallback

-- 建立維度表
CREATE TABLE IF NOT EXISTS silver.dim_mfg_five_level (
    -- 主鍵
    line_name String,
    
    -- 五階維度 (Region → Vx → Plant → Factory → Line)
    region_code Nullable(String),
    region_name Nullable(String),
    vx_code Nullable(String),        -- 由業務邏輯決定，非 MDM
    vx_name Nullable(String),        -- V1/V2/V3 描述
    plant_code Nullable(String),
    plant_name Nullable(String),
    factory_code Nullable(String),
    factory_name Nullable(String),
    line_code String,                -- 等同於 line_name
    line_desc Nullable(String),
    
    -- 補充維度資訊
    mfg_site Nullable(String),       -- 製造基地
    country Nullable(String),        -- 國家
    prod_area_id Nullable(Int64),    -- 產區 ID
    prod_area_code Nullable(String), -- 產區代碼
    
    -- 資料品質標記
    is_valid UInt8 DEFAULT 1,        -- 是否為有效維度組合
    missing_reason Nullable(String), -- 缺失原因
    data_source Nullable(String),    -- 資料來源標記
    
    -- Metadata
    _create_time DateTime64(3) DEFAULT now64(3),
    _update_time DateTime64(3) DEFAULT now64(3)
    
) ENGINE = ReplacingMergeTree(_update_time)
ORDER BY (line_name);

-- 清空並重新載入維度表
TRUNCATE TABLE silver.dim_mfg_five_level;

-- 插入維度資料
INSERT INTO silver.dim_mfg_five_level
WITH 
-- Step 1: 從 LINE 開始，向上串接到 FACTORY
line_to_factory AS (
    SELECT 
        l.LINE_NAME as line_name,
        l.LINE_DESC as line_desc,
        l.PROD_AREA_ID as prod_area_id,
        p.FACTORY as factory_code,
        p.PROD_AREA_CODE as prod_area_code,
        p.PROD_AREA_DESC as factory_name,
        CASE 
            WHEN l.PROD_AREA_ID IS NULL THEN 'LINE_NO_PROD_AREA'
            WHEN p.FACTORY IS NULL THEN 'PROD_AREA_NO_FACTORY'
            ELSE NULL
        END as missing_reason_step1
    FROM bronze.common_mdm_line_desc_master l
    LEFT JOIN bronze.common_mdm_prod_area_master p 
        ON l.PROD_AREA_ID = p.PROD_AREA_ID
    WHERE l.VALID_FLAG = 'Y'
),

-- Step 2: 從 FACTORY 串接到 PLANT
factory_to_plant AS (
    SELECT 
        ltf.*,
        mp.MFG_PLANT_CODE as plant_code,
        mp.MFG_PLANT_DESC as plant_name,
        CASE 
            WHEN ltf.missing_reason_step1 IS NOT NULL THEN ltf.missing_reason_step1
            WHEN mp.MFG_PLANT_CODE IS NULL THEN 'FACTORY_NO_PLANT'
            ELSE NULL
        END as missing_reason_step2
    FROM line_to_factory ltf
    LEFT JOIN bronze.common_mdm_mfg_plant_master mp
        ON ltf.factory_code = mp.FACTORY
        AND mp.VALIDITY = 'Y'
),

-- Step 3: 從 FACTORY 串接到 REGION (使用 MFG_SITE 作為 Region)
factory_to_region AS (
    SELECT 
        ftp.*,
        fa.MFG_SITE as region_code,
        COALESCE(ms.MFG_SITE_DESC, fa.MFG_SITE) as region_name,
        fa.MFG_SITE as mfg_site,
        fa.COUNTRY as country,
        CASE 
            WHEN ftp.missing_reason_step2 IS NOT NULL THEN ftp.missing_reason_step2
            WHEN fa.MFG_SITE IS NULL THEN 'FACTORY_NO_MFG_SITE'
            ELSE NULL
        END as missing_reason_final
    FROM factory_to_plant ftp
    LEFT JOIN bronze.common_mdm_factory_area_master fa
        ON ftp.factory_code = fa.FACTORY
        AND fa.VALID = '1'
    LEFT JOIN bronze.common_mdm_mfg_site_master ms
        ON fa.MFG_SITE = ms.MFG_SITE
)

SELECT 
    line_name,
    
    -- 五階維度
    region_code,
    region_name,
    NULL as vx_code,        -- Vx 由業務邏輯決定，不在此處計算
    NULL as vx_name,
    plant_code,
    plant_name,
    factory_code,
    factory_name,
    line_name as line_code,
    line_desc,
    
    -- 補充維度
    mfg_site,
    country,
    prod_area_id,
    prod_area_code,
    
    -- 資料品質
    CASE WHEN missing_reason_final IS NULL THEN 1 ELSE 0 END as is_valid,
    missing_reason_final as missing_reason,
    'MDM_MASTER_TABLES' as data_source,
    
    now64(3) as _create_time,
    now64(3) as _update_time
    
FROM factory_to_region;

-- 檢查結果
SELECT 
    '維度表建立完成' as status,
    count() as total_lines,
    sum(is_valid) as valid_lines,
    round(sum(is_valid) * 100.0 / count(), 2) as valid_percentage
FROM silver.dim_mfg_five_level;

-- 檢查缺失原因分布
SELECT 
    missing_reason,
    count() as line_count,
    round(count() * 100.0 / (SELECT count() FROM silver.dim_mfg_five_level), 2) as percentage
FROM silver.dim_mfg_five_level
GROUP BY missing_reason
ORDER BY line_count DESC;