/**
 * L5 任務完成率 Cube - V2 Pivot 版 (Updated 2026-02-10)
 * 
 * 目的: 結合 "V2 邏輯" (Time Machine, 寬表計算) 與 "Pivot 結構" (長表展示)。
 * 用途: 專門提供給 Superset "Status Comparison" 報表使用，支援時間回溯與精準過濾。
 * 更新: 2026-02-10 - 補回 Month/Week/Day-7 全週期邏輯，確保與 V2 資料完全一致。
 */

cube(`L5TaskPeriodicV2Pivot`, {
    sql: `
    WITH 
        -- 1. 引用 V2 核心邏輯: 參數過濾與錨點判定
        params AS (
            SELECT 
                max(snapshot_date) as max_filtered_date,
                today() as sys_today
            FROM gold.rmv_l5_task_completion
            WHERE (
                ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.snapshotDate.filter('toString(snapshot_date)')}
                OR ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.snapshotDate.filter("formatDateTime(snapshot_date, '%Y-%m-%d 00:00:00.000000')")}
                OR ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.snapshotDate.filter("formatDateTime(snapshot_date, '%Y-%m-%dT00:00:00.000Z')")}
            )
              AND ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.diffVxType.filter('vx_type')}
        ),
        calc_anchor AS (
            SELECT 
                CASE 
                    WHEN max_filtered_date >= sys_today THEN sys_today 
                    ELSE max_filtered_date
                END as anchor_dt,
                sys_today
            FROM params
        ),
        base AS (
            SELECT *
            FROM gold.rmv_l5_task_completion
            CROSS JOIN calc_anchor
            WHERE snapshot_date >= toStartOfMonth(anchor_dt) - INTERVAL 1 MONTH
              AND snapshot_date <= toLastDayOfMonth(anchor_dt) + INTERVAL 1 MONTH
              AND ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodicV2Pivot.diffVxType.filter('vx_type')}
        ),

        -- 2. V2 核心邏輯: 計算 Wide Metrics (包含 Month, Week, Day-7)
        v2_wide_metrics AS (
            -- A. Month: 加總當月所有任務
            SELECT 
                'Month' as granularity, formatDateTime(anchor_dt, '%b.') as period_name, 1 as sort_order,
                vx_type, region, plant, factory, line, 
                anchor_dt as filter_date, anchor_dt as snapshot_date_real,
                sum(total_task) as total_qty, sum(todo_count) as todo_qty, sum(doing_count) as doing_qty,
                sum(doing_count + done_count) as doing_done_qty, sum(done_count) as done_qty, 
                argMax(acc_todo_doing, snapshot_date) as acc_qty,
                sum(total_task) as acc_total_qty
            FROM base CROSS JOIN calc_anchor
            WHERE snapshot_date >= toStartOfMonth(anchor_dt) AND snapshot_date <= anchor_dt
            GROUP BY vx_type, region, plant, factory, line, anchor_dt, period_name

            UNION ALL

            -- B. Week: 加總當週所有任務
            SELECT 
                'Week' as granularity, concat('W', toString(toWeek(snapshot_date, 1))) as period_name,
                CASE WHEN toWeek(snapshot_date, 1) = toWeek(anchor_dt, 1) THEN 2
                     WHEN toWeek(snapshot_date, 1) = toWeek(anchor_dt - INTERVAL 7 DAY, 1) THEN 3
                     ELSE 4 END as sort_order,
                vx_type, region, plant, factory, line,
                anchor_dt as filter_date, max(snapshot_date) as snapshot_date_real,
                sum(total_task) as total_qty, sum(todo_count) as todo_qty, sum(doing_count) as doing_qty,
                sum(doing_count + done_count) as doing_done_qty, sum(done_count) as done_qty, 
                argMax(acc_todo_doing, snapshot_date) as acc_qty,
                sum(total_task) as acc_total_qty
            FROM base CROSS JOIN calc_anchor
            WHERE (
                (toWeek(snapshot_date, 1) = toWeek(anchor_dt, 1) AND snapshot_date <= anchor_dt) OR 
                (toWeek(snapshot_date, 1) = toWeek(anchor_dt - INTERVAL 7 DAY, 1)) OR
                (toWeek(snapshot_date, 1) = toWeek(anchor_dt - INTERVAL 14 DAY, 1))
            )
            GROUP BY granularity, period_name, sort_order, vx_type, region, plant, factory, line, anchor_dt

            UNION ALL

            -- C. Day: 當日任務，但 Acc 使用 7 天滾動總量
            SELECT granularity, period_name, sort_order, vx_type, region, plant, factory, line, 
                   filter_date, snapshot_date_real,
                    total_qty, todo_qty, doing_qty, doing_done_qty, done_qty, acc_qty,
                   sum(total_qty) OVER (PARTITION BY vx_type, region, plant, factory, line ORDER BY snapshot_date_real ASC ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as acc_total_qty
            FROM (
                SELECT 'Day' as granularity, toString(snapshot_date) as period_name,
                       5 + dateDiff('day', snapshot_date, anchor_dt) as sort_order,
                       vx_type, region, plant, factory, line,
                       anchor_dt as filter_date, snapshot_date as snapshot_date_real,
                       total_task as total_qty, todo_count as todo_qty, doing_count as doing_qty,
                       (doing_count + done_count) as doing_done_qty, done_count as done_qty, acc_todo_doing as acc_qty
                FROM base CROSS JOIN calc_anchor
                WHERE snapshot_date BETWEEN (anchor_dt - INTERVAL 13 DAY) AND anchor_dt
            ) AS daily_stream
            WHERE snapshot_date_real BETWEEN (filter_date - INTERVAL 6 DAY) AND filter_date
        )

    -- 3. Pivot 邏輯: 將 Wide 轉為 Long (針對所有 Granularity)
    SELECT * FROM (
        -- 1. Total
        SELECT 
            vx_type, region, plant, factory, line, filter_date, snapshot_date_real,
            granularity, period_name, sort_order as period_sort,
            '1. Total Task' as status_name, total_qty as task_qty, 100.0 as task_pct, 1 as status_sort
        FROM v2_wide_metrics
        
        UNION ALL
        
        -- 2. Todo
        SELECT 
            vx_type, region, plant, factory, line, filter_date, snapshot_date_real,
            granularity, period_name, sort_order as period_sort,
            '2. Todo' as status_name, todo_qty as task_qty, 
            round(todo_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 2 as status_sort
        FROM v2_wide_metrics

        UNION ALL
        
        -- 3. Doing
        SELECT 
            vx_type, region, plant, factory, line, filter_date, snapshot_date_real,
            granularity, period_name, sort_order as period_sort,
            '3. Doing' as status_name, doing_qty as task_qty, 
            round(doing_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 3 as status_sort
        FROM v2_wide_metrics

        UNION ALL
        
        -- 4. Done
        SELECT 
            vx_type, region, plant, factory, line, filter_date, snapshot_date_real,
            granularity, period_name, sort_order as period_sort,
            '4. Done' as status_name, done_qty as task_qty, 
            round(done_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 4 as status_sort
        FROM v2_wide_metrics

        UNION ALL
        
        -- 5. Doing+Done
        SELECT 
            vx_type, region, plant, factory, line, filter_date, snapshot_date_real,
            granularity, period_name, sort_order as period_sort,
            '5. Doing+Done' as status_name, doing_done_qty as task_qty, 
            round(doing_done_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 5 as status_sort
        FROM v2_wide_metrics

        UNION ALL
        
        -- 6. Acc
        SELECT 
            vx_type, region, plant, factory, line, filter_date, snapshot_date_real,
            granularity, period_name, sort_order as period_sort,
            '6. Todo+Doing(Acc)' as status_name, acc_qty as task_qty, 
            round(acc_qty * 100.0 / nullIf(acc_total_qty, 0), 2) as task_pct, 6 as status_sort
        FROM v2_wide_metrics
    ) AS pivoted_result
    `,

    title: 'L5 任務完成率 (V2 Pivot)',
    description: '結合 V2 邏輯 (Time Machine) 與 Pivot 結構，供 Superset 狀態比較報表使用',

    measures: {
        taskQty: {
            type: `sum`,
            sql: `task_qty`,
            title: 'Task Qty',
        },
        taskPct: {
            type: `avg`,
            sql: `task_pct`,
            title: 'Task (%)'
        },
        // 用來排序 Period (Month, Week, Day...)
        periodSortOrder: {
            type: `max`,
            sql: `period_sort`,
            title: 'Period Sort (Hidden)'
        }
    },

    dimensions: {
        id: {
            sql: `concat(toString(snapshot_date_real), '_', region, '_', plant, '_', factory, '_', line, '_', vx_type, '_', status_name, '_', period_name)`,
            type: `string`,
            primaryKey: true,
        },

        // V2 核心: 透過 filter_date 作為 Anchor
        snapshotDate: {
            type: `string`,
            sql: `formatDateTime(filter_date, '%Y-%m-%d')`,
            title: '日期篩選(決定 Anchor)'
        },
        realSnapshotDate: { type: `time`, sql: `snapshot_date_real`, title: '實際資料日期' },

        granularity: { type: `string`, sql: `granularity`, title: '時間粒度' },
        periodName: { type: `string`, sql: `period_name`, title: '週期名稱' },

        statusName: {
            type: `string`,
            sql: `status_name`,
            title: '任務狀態',
        },

        sortOrder: {
            type: `number`,
            sql: `status_sort`,
            title: '狀態排序 (Hidden)',
        },

        // 五階組織維度
        diffVxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' },
        diffRegion: { type: `string`, sql: `region`, title: '地區' },
        diffPlant: { type: `string`, sql: `plant`, title: '廠區' },
        diffFactory: { type: `string`, sql: `factory`, title: '工廠' },
        diffLine: { type: `string`, sql: `line`, title: '線體' }
    }
});
