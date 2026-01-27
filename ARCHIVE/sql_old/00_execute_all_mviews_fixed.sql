-- ========================================
-- ClickHouse 金銀銅資料層完整執行腳本
-- ========================================
-- 用途：一次性執行所有必要的 SQL 建立完整資料倉儲
-- 修正版本：使用修正後的 Silver 層邏輯
-- 執行時間：約 10-30 分鐘（依資料量而定）

-- ========================================
-- 階段 1：Bronze 層（銅層）- 原始資料
-- ========================================

-- 1. 建立資料庫結構
SOURCE sql/01_create_database.sql;

-- 2. 建立 BPM 相關表（Flowable 資料）
SOURCE sql/02_create_bpm_tables.sql;

-- 3. 建立共用表（HR、MDM 等）
SOURCE sql/03_create_common_tables.sql;

-- ========================================
-- 階段 2：Silver 層（銀層）- 資料轉換
-- ========================================

-- 4. 建立 Silver 資料庫
SOURCE sql/04_create_silver_database.sql;

-- 5. 建立 Silver 第一層 MVIEW（基礎轉換）
SOURCE sql/11_create_silver_mviews_layer1.sql;

-- 6. 建立 Silver 第二層 MVIEW（修正版本）⭐
SOURCE sql/12_create_silver_mviews_layer2_fixed.sql;

-- 7. 建立製造五階維度
SOURCE sql/create_silver_dim_mfg_five_level.sql;

-- ========================================
-- 階段 3：Gold 層（金層）- 聚合指標
-- ========================================

-- 8. 建立 Gold 層 MVIEW（最終指標）
SOURCE sql/13_create_gold_mviews.sql;

-- ========================================
-- 階段 4：驗證檢查
-- ========================================

-- 9. 執行關鍵驗證查詢
SELECT '=== Bronze 層驗證 ===' AS stage;
SELECT 'Bronze 層 BPM 任務表' AS check_name, COUNT(*) AS record_count
FROM bronze.bpm_act_hi_taskinst;

SELECT '=== Silver 層驗證 ===' AS stage;
SELECT 'Silver 層事實表' AS check_name, COUNT(*) AS record_count
FROM silver.mv_fact_task_vx_attribution FINAL;

SELECT '=== 關鍵測試案例 ===' AS stage;
-- WJ2/NBU/E5 2025-12-25 應為 5 筆（與 MSSQL 一致）
SELECT 'WJ2/NBU/E5 2025-12-25 測試' AS check_name, COUNT(*) AS record_count
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE (
    toDate(task_create_time) = '2025-12-25'
    OR toDate(task_claim_time) = '2025-12-25'
    OR toDate(task_end_time) = '2025-12-25'
)
AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5';
-- 預期結果：5 筆

SELECT '=== Gold 層驗證 ===' AS stage;
SELECT 'Gold 層聚合表' AS check_name, COUNT(*) AS record_count
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL;

-- ========================================
-- 完成提示
-- ========================================
SELECT 
    '🎉 ClickHouse 金銀銅資料層建置完成' AS status,
    now() AS completion_time,
    'Bronze → Silver → Gold 資料流已建立' AS description;

SELECT 
    '📊 關鍵驗證' AS check_type,
    'WJ2/NBU/E5 2025-12-25 應為 5 筆記錄' AS expected_result,
    '與 MSSQL 參考查詢一致' AS validation_note;