-- ========================================
-- ISO Week 合規性驗證 SQL
-- ========================================

-- A) ISO Week 驗證 SQL
-- 測試日期：2025-09-29、2025-10-05、2025-10-27、2025-11-01
-- 驗證：是否落在正確 ISO 週，是否週一起算

SELECT 
    '=== ISO Week 驗證 ===' AS test_section,
    '' AS separator;

WITH test_dates AS (
    SELECT arrayJoin([
        '2025-09-29',  -- 週一
        '2025-10-05',  -- 週日
        '2025-10-27',  -- 週一
        '2025-11-01'   -- 週六
    ]) AS test_date_str
),
test_results AS (
    SELECT 
        test_date_str,
        toDate(test_date_str) AS test_date,
        toDayOfWeek(toDate(test_date_str)) AS day_of_week,  -- 1=週一, 7=週日
        toISOWeek(toDate(test_date_str)) AS iso_week,
        toWeek(toDate(test_date_str), 1) AS iso_week_mode1,  -- 明確指定 ISO mode
        toWeek(toDate(test_date_str)) AS default_week,       -- 預設 mode (非 ISO)
        
        -- 計算該週的週一和週日
        toMonday(toDate(test_date_str)) AS week_monday,
        toMonday(toDate(test_date_str)) + INTERVAL 6 DAY AS week_sunday,
        
        -- 驗證是否為週一起算
        CASE 
            WHEN toDayOfWeek(toDate(test_date_str)) = 1 THEN 'Monday (Week Start)'
            WHEN toDayOfWeek(toDate(test_date_str)) = 7 THEN 'Sunday (Week End)'
            ELSE CONCAT('Weekday ', toString(toDayOfWeek(toDate(test_date_str))))
        END AS day_type
    FROM test_dates
)
SELECT 
    test_date_str,
    test_date,
    day_type,
    iso_week,
    iso_week_mode1,
    default_week,
    week_monday,
    week_sunday,
    
    -- 驗證結果
    CASE 
        WHEN iso_week = iso_week_mode1 THEN '✅ ISO Week 一致'
        ELSE '❌ ISO Week 不一致'
    END AS iso_consistency,
    
    CASE 
        WHEN iso_week != default_week THEN '✅ ISO 與預設不同 (正確)'
        ELSE '⚠️ ISO 與預設相同 (需檢查)'
    END AS iso_vs_default
FROM test_results
ORDER BY test_date;

-- B) W-pattern 驗證 SQL
-- 測試：today = 2025-11-01, query_month = 2025-11 → x = 44, query_month = 2025-10 → x = 44

SELECT 
    '' AS separator,
    '=== W-pattern 驗證 ===' AS test_section,
    '' AS separator2;

WITH w_pattern_test AS (
    SELECT 
        '2025-11-01' AS today_str,
        toDate('2025-11-01') AS today_date,
        toISOWeek(toDate('2025-11-01')) AS current_week,
        
        -- 測試當前月份 (2025-11)
        '2025-11' AS query_month_current,
        toISOWeek(toDate('2025-11-01')) AS x_current_month,  -- 當前日期所屬週次
        
        -- 測試歷史月份 (2025-10)
        '2025-10' AS query_month_history,
        toISOWeek(toLastDayOfMonth(toDate('2025-10-01'))) AS x_history_month,  -- 該月最後一日所屬週次
        
        -- W-pattern 計算
        CONCAT('W', toString(toISOWeek(toDate('2025-11-01')))) AS w_current,
        CONCAT('W', toString(toISOWeek(toDate('2025-11-01')) - 1)) AS w43_current,
        CONCAT('W', toString(toISOWeek(toDate('2025-11-01')) - 2)) AS w42_current,
        
        CONCAT('W', toString(toISOWeek(toLastDayOfMonth(toDate('2025-10-01'))))) AS w_history,
        CONCAT('W', toString(toISOWeek(toLastDayOfMonth(toDate('2025-10-01'))) - 1)) AS w43_history,
        CONCAT('W', toString(toISOWeek(toLastDayOfMonth(toDate('2025-10-01'))) - 2)) AS w42_history
)
SELECT 
    today_str,
    current_week,
    
    -- 當前月份測試
    query_month_current,
    x_current_month,
    w_current,
    w43_current,
    w42_current,
    
    -- 歷史月份測試
    query_month_history,
    x_history_month,
    w_history,
    w43_history,
    w42_history,
    
    -- 驗證 x 是否相同（應該不同）
    CASE 
        WHEN x_current_month != x_history_month THEN '✅ x 值不同 (正確)'
        ELSE '❌ x 值相同 (錯誤)'
    END AS x_validation
FROM w_pattern_test;

-- C) Dn-1 驗證 SQL
-- 驗證：當月 → today-1, 歷史月 → 月底

SELECT 
    '' AS separator,
    '=== Dn-1 驗證 ===' AS test_section,
    '' AS separator2;

WITH dn_pattern_test AS (
    SELECT 
        '2025-11-01' AS today_str,
        toDate('2025-11-01') AS today_date,
        
        -- 當月查詢 (2025-11)
        '2025-11' AS query_month_current,
        toDate('2025-11-01') - INTERVAL 1 DAY AS d0_current,  -- today - 1
        toDate('2025-11-01') - INTERVAL 2 DAY AS d1_current,  -- today - 2
        toDate('2025-11-01') - INTERVAL 3 DAY AS d2_current,  -- today - 3
        
        -- 歷史月查詢 (2025-10)
        '2025-10' AS query_month_history,
        toLastDayOfMonth(toDate('2025-10-01')) AS d0_history,  -- 月底
        toLastDayOfMonth(toDate('2025-10-01')) - INTERVAL 1 DAY AS d1_history,  -- 月底 - 1
        toLastDayOfMonth(toDate('2025-10-01')) - INTERVAL 2 DAY AS d2_history   -- 月底 - 2
)
SELECT 
    today_str,
    
    -- 當月 Dn-1 模式
    query_month_current,
    d0_current,
    d1_current,
    d2_current,
    
    -- 歷史月 Dn-1 模式
    query_month_history,
    d0_history,
    d1_history,
    d2_history,
    
    -- 驗證邏輯
    CASE 
        WHEN toYYYYMM(d0_current) = toYYYYMM(today_date) THEN '✅ 當月 D0 正確'
        ELSE '❌ 當月 D0 錯誤'
    END AS current_month_validation,
    
    CASE 
        WHEN d0_history = toLastDayOfMonth(toDate('2025-10-01')) THEN '✅ 歷史月 D0 正確'
        ELSE '❌ 歷史月 D0 錯誤'
    END AS history_month_validation
FROM dn_pattern_test;

-- D) 週次範圍驗證
-- 驗證 W40 = 2025/09/29(一) ～ 2025/10/05(日)

SELECT 
    '' AS separator,
    '=== 週次範圍驗證 ===' AS test_section,
    '' AS separator2;

WITH week_range_test AS (
    SELECT 
        40 AS target_week,
        toDate('2025-09-29') AS expected_monday,
        toDate('2025-10-05') AS expected_sunday,
        
        -- 找到 2025 年第 40 週的實際範圍
        toMonday(toDate('2025-09-29')) AS actual_monday,
        toMonday(toDate('2025-09-29')) + INTERVAL 6 DAY AS actual_sunday,
        
        toISOWeek(toDate('2025-09-29')) AS monday_week,
        toISOWeek(toDate('2025-10-05')) AS sunday_week
)
SELECT 
    target_week,
    expected_monday,
    expected_sunday,
    actual_monday,
    actual_sunday,
    monday_week,
    sunday_week,
    
    -- 驗證結果
    CASE 
        WHEN expected_monday = actual_monday AND expected_sunday = actual_sunday THEN '✅ 週次範圍正確'
        ELSE '❌ 週次範圍錯誤'
    END AS range_validation,
    
    CASE 
        WHEN monday_week = sunday_week AND monday_week = target_week THEN '✅ 週次一致'
        ELSE '❌ 週次不一致'
    END AS week_consistency
FROM week_range_test;

SELECT 
    '' AS separator,
    '=== 驗證完成 ===' AS completion,
    '' AS separator2;