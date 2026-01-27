-- ========================================
-- MView 完整建立腳本 - 執行順序
-- ========================================
-- 用途：按正確順序建立所有 Materialized Views
-- 執行方式：依序執行以下 SQL 檔案
-- 注意：必須按順序執行，因為存在依賴關係

-- ========================================
-- 執行順序說明
-- ========================================
/*
1. 11_create_silver_mviews_layer1.sql  - Silver 層第一層（基礎聚合）
2. 12_create_silver_mviews_layer2.sql  - Silver 層第二層（業務邏輯）
3. 13_create_gold_mviews.sql           - Gold 層（最終指標）

依賴關係：
- Layer 2 依賴 Layer 1
- Gold 層依賴 Silver 層
- 所有層級都依賴 Bronze 層資料
*/

-- ========================================
-- 快速驗證腳本
-- ========================================
-- 執行完成後，可以使用以下查詢驗證結果

-- 1. 檢查所有 MView 是否建立成功
SELECT 
    database,
    name,
    engine,
    total_rows
FROM system.tables
WHERE database IN ('silver', 'gold')
    AND engine LIKE '%View%'
ORDER BY database, name;

-- 2. 檢查 NPE 資料是否正確
SELECT 
    'Silver Layer - mv_fact_task_vx_attribution' AS layer,
    vx_subtype,
    COUNT(*) as count
FROM silver.mv_fact_task_vx_attribution
WHERE vx_type = 'V1'
GROUP BY vx_subtype
ORDER BY vx_subtype

UNION ALL

SELECT 
    'Silver Layer - mv_l5_metrics_realtime' AS layer,
    vx_subtype,
    SUM(total_task_qty) as count
FROM silver.mv_l5_metrics_realtime
WHERE vx_type = 'V1'
GROUP BY vx_subtype
ORDER BY vx_subtype

UNION ALL

SELECT 
    'Gold Layer - DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV' AS layer,
    vx_subtype,
    SUM(sum_total_task_qty) as count
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
WHERE vx_type = 'V1'
GROUP BY vx_subtype
ORDER BY vx_subtype;

-- 3. 檢查 315% 規則是否正確應用
SELECT 
    'mv_fact_task_vx_attribution' AS table_name,
    COUNT(*) as total_315_orders,
    COUNT(DISTINCT mo_number) as unique_mo_numbers
FROM silver.mv_fact_task_vx_attribution
WHERE mo_number LIKE '315%';

-- 4. 檢查所有 MView 的資料量
SELECT 
    'silver.mv_varinst_pivoted' AS table_name,
    COUNT(*) as row_count,
    COUNT(CASE WHEN varinst_name LIKE '%NPE%' THEN 1 END) as npe_count
FROM silver.mv_varinst_pivoted

UNION ALL

SELECT 
    'silver.mv_fact_task_vx_attribution' AS table_name,
    COUNT(*) as row_count,
    COUNT(CASE WHEN vx_subtype = 'V1_NPE' THEN 1 END) as npe_count
FROM silver.mv_fact_task_vx_attribution

UNION ALL

SELECT 
    'silver.mv_l5_metrics_realtime' AS table_name,
    COUNT(*) as row_count,
    SUM(CASE WHEN vx_subtype = 'V1_NPE' THEN total_task_qty ELSE 0 END) as npe_count
FROM silver.mv_l5_metrics_realtime

UNION ALL

SELECT 
    'gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV' AS table_name,
    COUNT(*) as row_count,
    SUM(CASE WHEN vx_subtype = 'V1_NPE' THEN sum_total_task_qty ELSE 0 END) as npe_count
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;

-- ========================================
-- 預期結果
-- ========================================
/*
執行成功後，應該看到：

1. MView 建立狀態：
   - silver.mv_varinst_pivoted: ~17,949 行（包含 NPE 資料）
   - silver.mv_fact_task_vx_attribution: ~1,300,963 行
   - silver.mv_l5_metrics_realtime: ~9,996 行
   - gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV: ~299 行

2. NPE 資料驗證：
   - V1_NPE: 應該 > 0（約 283-95 筆，視聚合層級而定）
   - V1_MFG: 應該 > 0（約 1,008,774-694,004 筆，視聚合層級而定）

3. 315% 規則驗證：
   - 315% 工單總數: ~489,515 筆
   - 315% 唯一工單號: ~2,151 個

如果任何數值為 0 或明顯異常，請檢查：
- Bronze 層資料是否完整
- SQL 執行順序是否正確
- 是否有語法錯誤
*/