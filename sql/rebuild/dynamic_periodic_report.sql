/*
 * L5 任務週期報表 (ClickHouse Logic Push-down Standard)
 * 
 * [架構說明]
 * 適用流程: ClickHouse -> Cube.js -> Superset
 * 核心機制: "Parameter Inference" (參數推論)
 * 
 * [如何運作]
 * 1. 本 SQL 不依賴 Superset 變數 ({{...}})。
 * 2. 而是利用 SQL 查詢時的 `WHERE` 條件範圍，自動偵測使用者的意圖。
 * 3. Cube.js 會將前端 Filter 注入到 `base` CTE 中。
 * 4. SQL 內部的 `params` CTE 會計算該範圍的 `max(snapshot_date)`：
 *    - 若範圍涵蓋今日 -> 判斷為「當月模式」
 *    - 若範圍全為過去 -> 判斷為「歷史模式」
 */

WITH 
    -- 1. 基礎資料集 (Base Data)
    -- Cube.js 的 FILTER_PARAMS 會自動注入到這裡的 WHERE 子句
    base AS (
        SELECT *
        FROM gold.rmv_l5_task_completion
        WHERE 1=1
          -- [Placeholder] cube.js 會在此插入篩選條件
          -- AND snapshot_date BETWEEN '...'
          -- AND region = '...'
    ),

    -- 2. 參數偵測 (從 Base Data 中抓取使用者意圖)
    params AS (
        SELECT 
            -- 抓取「篩選後」資料的最大日期作為 Anchor 線索
            -- 如果 Cube 有過濾日期，這裡抓到的就是該範圍的最後一天
            max(snapshot_date) as max_filtered_date,
            today() as sys_today
        FROM base
    ),

    -- 3. 決定基準日 (Anchor Logic)
    calc_anchor AS (
        SELECT 
            CASE 
                -- 情況 A: 篩選範圍為空 (無資料) -> 預設今天
                WHEN max_filtered_date IS NULL THEN sys_today
                
                -- 情況 B: 篩選範圍包含今天或未來 -> 當月模式 (Anchor = Today)
                WHEN max_filtered_date >= sys_today THEN sys_today 
                
                -- 情況 C: 篩選範圍都是過去 -> 歷史模式 (Anchor = 該範圍從屬月份的最後一天)
                ELSE toLastDayOfMonth(max_filtered_date)
            END as anchor_dt,
            sys_today
        FROM params
    )

-- 4. 組合三種粒度 (UNION ALL)

-- A. 月份粒度 (Month)
SELECT 
    'Month' as granularity,
    formatDateTime(anchor_dt, '%b.') as period_name,
    1 as sort_order,

    vx_type, region, plant, factory, line,

    sum(total_task) as total_qty,
    sum(todo_count) as todo_qty,
    sum(doing_count) as doing_qty,
    sum(doing_count + done_count) as doing_done_qty,
    sum(done_count) as done_qty,
    sum(acc_todo_doing) as acc_qty,

    round(sum(todo_count) * 100.0 / nullIf(sum(total_task), 0), 2) as todo_rate,
    round(sum(doing_count) * 100.0 / nullIf(sum(total_task), 0), 2) as doing_rate,
    round(sum(doing_count + done_count) * 100.0 / nullIf(sum(total_task), 0), 2) as doing_done_rate,
    round(sum(done_count) * 100.0 / nullIf(sum(total_task), 0), 2) as done_rate,
    round(sum(acc_todo_doing) * 100.0 / nullIf(sum(total_task), 0), 2) as acc_rate

FROM base CROSS JOIN calc_anchor
WHERE snapshot_date >= toStartOfMonth(anchor_dt)
  AND snapshot_date <= anchor_dt
GROUP BY vx_type, region, plant, factory, line, anchor_dt, period_name

UNION ALL

-- B. 週粒度 (Week)
SELECT 
    'Week' as granularity,
    concat('W', toString(toWeek(snapshot_date, 1))) as period_name,
    CASE 
        WHEN toWeek(snapshot_date, 1) = toWeek(anchor_dt, 1) THEN 2
        WHEN toWeek(snapshot_date, 1) = toWeek(anchor_dt - 7, 1) THEN 3
        ELSE 4
    END as sort_order,

    vx_type, region, plant, factory, line,

    sum(total_task) as total_qty,
    sum(todo_count) as todo_qty,
    sum(doing_count) as doing_qty,
    sum(doing_count + done_count) as doing_done_qty,
    sum(done_count) as done_qty,
    sum(acc_todo_doing) as acc_qty,

    round(sum(todo_count) * 100.0 / nullIf(sum(total_task), 0), 2) as todo_rate,
    round(sum(doing_count) * 100.0 / nullIf(sum(total_task), 0), 2) as doing_rate,
    round(sum(doing_count + done_count) * 100.0 / nullIf(sum(total_task), 0), 2) as doing_done_rate,
    round(sum(done_count) * 100.0 / nullIf(sum(total_task), 0), 2) as done_rate,
    round(sum(acc_todo_doing) * 100.0 / nullIf(sum(total_task), 0), 2) as acc_rate

FROM base CROSS JOIN calc_anchor
WHERE snapshot_date >= toStartOfWeek(anchor_dt, 1) - INTERVAL 14 DAY
  AND snapshot_date <  toStartOfWeek(anchor_dt, 1) + INTERVAL 7 DAY
GROUP BY period_name, sort_order, granularity, vx_type, region, plant, factory, line

UNION ALL

-- C. 日粒度 (Day)
SELECT 
    'Day' as granularity,
    toString(snapshot_date) as period_name,
    5 + dateDiff('day', snapshot_date, anchor_dt) as sort_order,

    vx_type, region, plant, factory, line,

    total_task as total_qty,
    todo_count as todo_qty,
    doing_count as doing_qty,
    (doing_count + done_count) as doing_done_qty,
    done_count as done_qty,
    acc_todo_doing as acc_qty,

    round(todo_count * 100.0 / nullIf(total_task, 0), 2) as todo_rate,
    round(doing_count * 100.0 / nullIf(total_task, 0), 2) as doing_rate,
    round((doing_count + done_count) * 100.0 / nullIf(total_task, 0), 2) as doing_done_rate,
    round(done_count * 100.0 / nullIf(total_task, 0), 2) as done_rate,
    round(acc_todo_doing * 100.0 / nullIf(total_task, 0), 2) as acc_rate

FROM base CROSS JOIN calc_anchor
WHERE snapshot_date BETWEEN (anchor_dt - INTERVAL 6 DAY) AND anchor_dt

ORDER BY sort_order;
