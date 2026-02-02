-- ========================================
-- 步驟 8: 驗證資料一致性
-- 執行時間: 約 2 分鐘
-- 目的: 確認新舊資料一致
-- ========================================

-- ========================================
-- 8.1 資料量對比
-- ========================================
SELECT '新表 silver.mv_fact_task_vx' AS source, count() AS row_count 
FROM silver.mv_fact_task_vx FINAL
UNION ALL
SELECT '舊表 silver.FACT_TASK_VX_ATTRIBUTION_backup', count() 
FROM silver.FACT_TASK_VX_ATTRIBUTION_backup_20260129;

-- ========================================
-- 8.2 Vx 分布對比
-- ========================================
SELECT 
    '新表' AS source,
    vx_type,
    count() AS cnt
FROM silver.mv_fact_task_vx FINAL
WHERE task_create_date = '2025-12-31'
GROUP BY vx_type
ORDER BY vx_type;

-- ========================================
-- 8.3 特定條件對比 (CNE WJ2 NBU E5)
-- ========================================
SELECT 
    '新表' AS source,
    vx_type,
    task_status,
    count() AS cnt
FROM silver.mv_fact_task_vx FINAL
WHERE region = 'CNE' 
  AND plant = 'WJ2' 
  AND factory = 'NBU' 
  AND line = 'E5'
  AND task_create_date = '2025-12-31'
GROUP BY vx_type, task_status
ORDER BY vx_type, task_status;

-- ========================================
-- 8.4 Gold 層資料驗證
-- ========================================
SELECT 
    snapshot_date,
    vx_type,
    sum(total_task) AS total,
    sum(done_count) AS done,
    round(sum(done_count) * 100.0 / sum(total_task), 2) AS completion_rate
FROM gold.rmv_l5_task_completion
WHERE snapshot_date = '2025-12-31'
GROUP BY snapshot_date, vx_type
ORDER BY vx_type;

-- ========================================
-- 8.5 REFRESHABLE MView 狀態檢查
-- ========================================
SELECT 
    database, view,
    status,
    last_refresh_time,
    next_refresh_time,
    last_refresh_result
FROM system.view_refreshes
WHERE database = 'gold';

-- ========================================
-- 8.6 資料延遲檢查
-- ========================================
SELECT 
    'silver.mv_varinst_pivoted' AS mview,
    max(_mview_update_time) AS last_update,
    dateDiff('minute', max(_mview_update_time), now()) AS delay_minutes
FROM silver.mv_varinst_pivoted
UNION ALL
SELECT 
    'silver.mv_fact_task_vx',
    max(_mview_update_time),
    dateDiff('minute', max(_mview_update_time), now())
FROM silver.mv_fact_task_vx
UNION ALL  
SELECT
    'gold.rmv_l5_task_completion',
    max(_refresh_time),
    dateDiff('minute', max(_refresh_time), now())
FROM gold.rmv_l5_task_completion
UNION ALL
SELECT
    'gold.rmv_user_utilization',
    max(_refresh_time),
    dateDiff('minute', max(_refresh_time), now())
FROM gold.rmv_user_utilization;

SELECT '驗證完成' AS status;
