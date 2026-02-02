-- ========================================
-- 步驟 1: Bronze 層加入 TTL 1 年
-- 執行時間: 約 1 分鐘
-- ========================================

-- 1.1 bpm_act_hi_taskinst (任務實例歷史)
ALTER TABLE bronze.bpm_act_hi_taskinst
MODIFY TTL toDate(START_TIME_) + INTERVAL 1 YEAR;

-- 1.2 bpm_act_hi_varinst (變數實例歷史)
ALTER TABLE bronze.bpm_act_hi_varinst
MODIFY TTL toDate(CREATE_TIME_) + INTERVAL 1 YEAR;

-- 1.3 bpm_act_hi_procinst (流程實例歷史)
ALTER TABLE bronze.bpm_act_hi_procinst
MODIFY TTL toDate(START_TIME_) + INTERVAL 1 YEAR;

-- 1.4 _sync_watermark (同步水位線)
ALTER TABLE bronze._sync_watermark
MODIFY TTL toDate(sync_time) + INTERVAL 1 YEAR;

-- 驗證 TTL 設定
SELECT 
    database, name, 
    engine,
    data_paths[1] AS data_path
FROM system.tables 
WHERE database = 'bronze' 
  AND name IN ('bpm_act_hi_taskinst', 'bpm_act_hi_varinst', 'bpm_act_hi_procinst', '_sync_watermark');

SELECT 'Bronze TTL 設定完成' AS status;
