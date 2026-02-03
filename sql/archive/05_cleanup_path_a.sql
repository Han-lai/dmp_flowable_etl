-- ========================================
-- 步驟 7: 清理舊 Path A 表
-- 執行時間: 約 1 分鐘
-- 注意: 請先確認新表資料正確後再執行此腳本
-- ========================================

-- ========================================
-- 7.1 備份舊表（重命名）
-- ========================================

-- Silver 層舊表備份
ALTER TABLE silver.FACT_TASK_VX_ATTRIBUTION 
RENAME TO silver.FACT_TASK_VX_ATTRIBUTION_backup_20260129;

ALTER TABLE silver.DIM_CONFIG_USER 
RENAME TO silver.DIM_CONFIG_USER_backup_20260129;

-- Gold 層舊表備份
ALTER TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT 
RENAME TO gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_backup_20260129;

ALTER TABLE gold.DAILY_USER_UTILIZATION_SNAPSHOT 
RENAME TO gold.DAILY_USER_UTILIZATION_SNAPSHOT_backup_20260129;

ALTER TABLE gold.l5_dashboard_summary 
RENAME TO gold.l5_dashboard_summary_backup_20260129;

-- ========================================
-- 7.2 移除舊 View（如果存在）
-- ========================================
DROP VIEW IF EXISTS gold.v_l5_dashboard_summary_populate;

-- ========================================
-- 7.3 確認清理結果
-- ========================================
SELECT 
    database, name, engine
FROM system.tables 
WHERE (database = 'silver' OR database = 'gold')
  AND name LIKE '%backup%'
ORDER BY database, name;

SELECT 'Path A 舊表已備份完成' AS status;

-- ========================================
-- 7.4 確認無問題後，刪除備份表（可選）
-- 建議保留 7 天後再執行以下刪除
-- ========================================
-- DROP TABLE IF EXISTS silver.FACT_TASK_VX_ATTRIBUTION_backup_20260129;
-- DROP TABLE IF EXISTS silver.DIM_CONFIG_USER_backup_20260129;
-- DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_backup_20260129;
-- DROP TABLE IF EXISTS gold.DAILY_USER_UTILIZATION_SNAPSHOT_backup_20260129;
-- DROP TABLE IF EXISTS gold.l5_dashboard_summary_backup_20260129;
