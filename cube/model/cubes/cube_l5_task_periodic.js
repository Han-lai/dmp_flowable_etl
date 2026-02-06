/**
 * L5 任務完成率 (週期報表動態版)
 * 
 * 用途: 支援在同一個圖表的 X 軸顯示 [Month, Week, Day] 的混合維度。
 * 邏輯: 自動根據使用者在 Superset 選擇的日期範圍（或最大日期）作為 Anchor，
 *       往前計算該月、前三週、以及最近七天的數據。
 */

cube(`L5TaskPeriodic`, {
    sql: `
    WITH base AS (
        SELECT * FROM gold.rmv_l5_task_completion FINAL
    ),
    -- 1. 核心：找出 Anchor Date (篩選範圍內的最大日期)
    anchor_info AS (
        -- 如果使用者有篩選日期，取篩選範圍的最大值；否則取全表最大值
        SELECT max(snapshot_date) as anchor_dt
        FROM base
    ),
    -- 2. 計算各個週期的名稱與範圍
    calc_meta AS (
        SELECT 
            anchor_dt,
            -- 月份
            formatDateTime(anchor_dt, '%b.') as m_name,
            toStartOfMonth(anchor_dt) as m_start,
            addMonths(m_start, 1) as m_end,
            -- 週別 (ISO Week -> Compatible)
            concat('W', toString(toWeek(anchor_dt, 1))) as w0_name,
            toStartOfWeek(anchor_dt, 1) as w0_start,
            concat('W', toString(toWeek(anchor_dt - interval 7 day, 1))) as w1_name,
            toStartOfWeek(anchor_dt - interval 7 day, 1) as w1_start,
            concat('W', toString(toWeek(anchor_dt - interval 14 day, 1))) as w2_name,
            toStartOfWeek(anchor_dt - interval 14 day, 1) as w2_start
        FROM anchor_info
    )

    -- --- 3. 組合數據 (UNION ALL) ---

    -- A. 月份數據
    SELECT 
        m_name as period_name, 1 as sort_order, 
        vx_type, region, plant, factory, line,
        sum(total_task) as total_qty, sum(done_count) as done_qty, sum(doing_count) as doing_qty, sum(todo_count) as todo_qty,
        sum(acc_todo_doing) as acc_qty
    FROM base CROSS JOIN calc_meta
    WHERE snapshot_date >= m_start AND snapshot_date < m_end
    GROUP BY m_name, vx_type, region, plant, factory, line

    UNION ALL

    -- B. 週別數據 (當週 + 前兩週)
    SELECT 
        CASE 
            WHEN snapshot_date >= w0_start THEN w0_name
            WHEN snapshot_date >= w1_start THEN w1_name
            ELSE w2_name
        END as period_name,
        CASE 
            WHEN snapshot_date >= w0_start THEN 2
            WHEN snapshot_date >= w1_start THEN 3
            ELSE 4
        END as sort_order,
        vx_type, region, plant, factory, line,
        sum(total_task) as total_qty, sum(done_count) as done_qty, sum(doing_count) as doing_qty, sum(todo_count) as todo_qty,
        sum(acc_todo_doing) as acc_qty
    FROM base CROSS JOIN calc_meta
    WHERE (snapshot_date >= w0_start AND snapshot_date < w0_start + interval 7 day)
       OR (snapshot_date >= w1_start AND snapshot_date < w1_start + interval 7 day)
       OR (snapshot_date >= w2_start AND snapshot_date < w2_start + interval 7 day)
    GROUP BY period_name, sort_order, vx_type, region, plant, factory, line

    UNION ALL

    -- C. 日期數據 (最近 8 天)
    SELECT 
        toString(snapshot_date) as period_name,
        5 + (anchor_dt - snapshot_date) as sort_order,
        vx_type, region, plant, factory, line,
        total_task as total_qty, done_count as done_qty, doing_count as doing_qty, todo_count as todo_qty,
        acc_todo_doing as acc_qty
    FROM base CROSS JOIN calc_meta
    WHERE snapshot_date BETWEEN (anchor_dt - interval 7 day) AND anchor_dt
    `,

    title: 'L5 任務週期對比報表 (動態 X 軸)',
    description: '自動根據所選日期區間的最大值作為基準，產出月份、三週、以及最近七天的指標數據。',

    measures: {
        totalQty: { type: `sum`, sql: `total_qty`, title: 'QTY: Total' },
        doneQty: { type: `sum`, sql: `done_qty`, title: 'QTY: Done' },
        doingQty: { type: `sum`, sql: `doing_qty`, title: 'QTY: Doing' },
        todoQty: { type: `sum`, sql: `todo_qty`, title: 'QTY: Todo' },
        todoDoingQty: { type: `number`, sql: `${todoQty} + ${doingQty}`, title: 'QTY: Todo + Doing' },
        doingDoneQty: { type: `number`, sql: `${doingQty} + ${doneQty}`, title: 'QTY: Doing + Done' },
        accQty: { type: `sum`, sql: `acc_qty`, title: 'QTY: Todo+Doing(Acc)' },

        doneRate: {
            type: `number`,
            sql: `round(sum(done_qty) * 100.0 / nullIf(sum(total_qty), 0), 2)`,
            title: 'Rate: Done',
        },
        doingRate: {
            type: `number`,
            sql: `round(sum(doing_qty) * 100.0 / nullIf(sum(total_qty), 0), 2)`,
            title: 'Rate: Doing',
        },
        todoRate: {
            type: `number`,
            sql: `round(sum(todo_qty) * 100.0 / nullIf(sum(total_qty), 0), 2)`,
            title: 'Rate: Todo',
        },
        todoDoingRate: {
            type: `number`,
            sql: `round((sum(todo_qty) + sum(doing_qty)) * 100.0 / nullIf(sum(total_qty), 0), 2)`,
            title: 'Rate: Todo + Doing',
        },
        doingDoneRate: {
            type: `number`,
            sql: `round((sum(doing_qty) + sum(done_qty)) * 100.0 / nullIf(sum(total_qty), 0), 2)`,
            title: 'Rate: Doing + Done',
        },

        // --- 排序輔助指標 ---
        periodSortOrder: {
            type: `max`,
            sql: `sort_order`,
            title: '排序用(Hidden)',
            description: '請在 Superset 圖表的 Sort By 欄位使用此指標 (Ascending) 以達成正確的混合排序'
        }
    },

    dimensions: {
        periodName: {
            type: `string`,
            sql: `period_name`,
            title: '週期/日期',
        },
        sortOrder: {
            type: `number`,
            sql: `sort_order`,
            title: '排序序號',
        },
        snapshotDate: {
            type: `time`,
            sql: `snapshot_date`,
            title: '快照日期過濾器',
        },
        vxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' },
        region: { type: `string`, sql: `region`, title: '地區' },
        plant: { type: `string`, sql: `plant`, title: '廠區' },
        factory: { type: `string`, sql: `factory`, title: '工廠' },
        line: { type: `string`, sql: `line`, title: '線體' }
    }
});