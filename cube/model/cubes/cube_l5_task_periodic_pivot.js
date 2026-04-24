/**
 * L5 任務完成率 Cube - Pivot 版 (V3 Bitmap Version)
 * 
 * 目的: 結合 "核心邏輯" (Time Machine, 寬表計算) 與 "Pivot 結構" (長表展示)。
 * 更新: 全面升級至 Bitmap 函數，對齊 gold.rmv_l5_task_completion 結構。
 */

cube(`L5TaskPeriodicPivot`, {
    sql: `
    WITH 
        params AS (
            SELECT 
                max(snapshot_date) as max_filtered_date,
                today() as sys_today
            FROM gold.rmv_l5_task_completion
            WHERE (
                ${FILTER_PARAMS.L5TaskPeriodicPivot.snapshotDate.filter('snapshot_date')}
            )
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffVxType.filter('vx_type')}
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
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffVxType.filter('vx_type')}
        ),

        v2_wide_metrics AS (
            -- A. Month: 加總當月所有任務
            SELECT 
                'Month' as granularity, formatDateTime(anchor_dt, '%b.') as period_name, 1 as sort_order,
                vx_type, region, plant, factory, line, 
                anchor_dt as filter_date, anchor_dt as snapshot_date_real,
                bitmapCardinality(groupBitmapMergeState(total_task)) as total_qty, 
                bitmapCardinality(bitmapAndnot(groupBitmapMergeState(todo), bitmapOr(groupBitmapMergeState(doing), groupBitmapMergeState(done)))) as todo_qty, 
                bitmapCardinality(bitmapAndnot(groupBitmapMergeState(doing), groupBitmapMergeState(done))) as doing_qty,
                bitmapCardinality(bitmapOr(groupBitmapMergeState(doing), groupBitmapMergeState(done))) as doing_done_qty, 
                bitmapCardinality(groupBitmapMergeState(done)) as done_qty, 
                bitmapCardinality(bitmapAndnot(bitmapOr(groupBitmapMergeState(todo), groupBitmapMergeState(doing)), groupBitmapMergeState(done))) as acc_qty,
                bitmapCardinality(groupBitmapMergeState(total_task)) as acc_total_qty
            FROM base
            WHERE snapshot_date >= toStartOfMonth(anchor_dt) AND snapshot_date <= anchor_dt
            GROUP BY vx_type, region, plant, factory, line, anchor_dt, period_name

            UNION ALL

            -- B. Week: 加總當週所有任務
            SELECT 
                'Week' as granularity, concat('W', toString(toISOWeek(snapshot_date))) as period_name,
                CASE WHEN toISOWeek(snapshot_date) = toISOWeek(anchor_dt) THEN 2
                     WHEN toISOWeek(snapshot_date) = toISOWeek(anchor_dt - INTERVAL 7 DAY) THEN 3
                     ELSE 4 END as sort_order,
                vx_type, region, plant, factory, line,
                anchor_dt as filter_date, max(snapshot_date) as snapshot_date_real,
                bitmapCardinality(groupBitmapMergeState(total_task)) as total_qty, 
                bitmapCardinality(bitmapAndnot(groupBitmapMergeState(todo), bitmapOr(groupBitmapMergeState(doing), groupBitmapMergeState(done)))) as todo_qty, 
                bitmapCardinality(bitmapAndnot(groupBitmapMergeState(doing), groupBitmapMergeState(done))) as doing_qty,
                bitmapCardinality(bitmapOr(groupBitmapMergeState(doing), groupBitmapMergeState(done))) as doing_done_qty, 
                bitmapCardinality(groupBitmapMergeState(done)) as done_qty, 
                bitmapCardinality(bitmapAndnot(bitmapOr(groupBitmapMergeState(todo), groupBitmapMergeState(doing)), groupBitmapMergeState(done))) as acc_qty,
                bitmapCardinality(groupBitmapMergeState(total_task)) as acc_total_qty
            FROM base
            WHERE (
                (toISOWeek(snapshot_date) = toISOWeek(anchor_dt) AND snapshot_date <= anchor_dt) OR 
                (toISOWeek(snapshot_date) = toISOWeek(anchor_dt - INTERVAL 7 DAY)) OR
                (toISOWeek(snapshot_date) = toISOWeek(anchor_dt - INTERVAL 14 DAY))
            )
            GROUP BY granularity, period_name, sort_order, vx_type, region, plant, factory, line, anchor_dt

            UNION ALL

            -- C. Day: 當日任務，Acc 使用 7 天滾動總量(來自金層 acc 狀態)
            SELECT 
                'Day' as granularity, toString(snapshot_date) as period_name,
                5 + dateDiff('day', snapshot_date, anchor_dt) as sort_order,
                vx_type, region, plant, factory, line,
                anchor_dt as filter_date, snapshot_date as snapshot_date_real,
                bitmapCardinality(groupBitmapMergeState(total_task)) as total_qty, 
                bitmapCardinality(bitmapAndnot(groupBitmapMergeState(todo), bitmapOr(groupBitmapMergeState(doing), groupBitmapMergeState(done)))) as todo_qty, 
                bitmapCardinality(bitmapAndnot(groupBitmapMergeState(doing), groupBitmapMergeState(done))) as doing_qty,
                bitmapCardinality(bitmapOr(groupBitmapMergeState(doing), groupBitmapMergeState(done))) as doing_done_qty, 
                bitmapCardinality(groupBitmapMergeState(done)) as done_qty, 
                bitmapCardinality(groupBitmapMergeState(acc)) as acc_qty,
                bitmapCardinality(groupBitmapMergeState(total_task)) as acc_total_qty
            FROM base
            WHERE snapshot_date BETWEEN (anchor_dt - INTERVAL 13 DAY) AND anchor_dt
            GROUP BY granularity, period_name, sort_order, vx_type, region, plant, factory, line, anchor_dt, snapshot_date
        )

    SELECT * FROM (
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '1. Total Task' as status_name, total_qty as task_qty, 100.0 as task_pct, 1 as status_sort FROM v2_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '2. Todo' as status_name, todo_qty as task_qty, round(todo_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 2 as status_sort FROM v2_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '3. Doing' as status_name, doing_qty as task_qty, round(doing_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 3 as status_sort FROM v2_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '4. Done' as status_name, done_qty as task_qty, round(done_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 4 as status_sort FROM v2_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '5. Doing+Done' as status_name, doing_done_qty as task_qty, round(doing_done_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 5 as status_sort FROM v2_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '6. Todo+Doing(Acc)' as status_name, acc_qty as task_qty, round(acc_qty * 100.0 / nullIf(acc_total_qty, 0), 2) as task_pct, 6 as status_sort FROM v2_wide_metrics
    ) AS pivoted_result
    `,

    title: 'L5 任務完成率 (Pivot)',
    description: '結合核心邏輯與 Pivot 結構，對接 V3 Bitmap 架構供狀態報表使用',

    measures: {
        taskQty: { type: `sum`, sql: `task_qty`, title: 'Task Qty' },
        taskPct: { type: `avg`, sql: `task_pct`, title: 'Task (%)' },
        periodSortOrder: { type: `max`, sql: `period_sort`, title: 'Period Sort (Hidden)' }
    },

    dimensions: {
        id: { sql: `concat(toString(snapshot_date_real), '_', region, '_', plant, '_', factory, '_', line, '_', vx_type, '_', status_name, '_', period_name)`, type: `string`, primaryKey: true },
        snapshotDate: { type: `time`, sql: `filter_date`, title: '日期篩選(決定 Anchor)' },
        realSnapshotDate: { type: `time`, sql: `snapshot_date_real`, title: '實際資料日期' },
        granularity: { type: `string`, sql: `granularity`, title: '時間粒度' },
        periodName: { type: `string`, sql: `period_name`, title: '週期名稱' },
        statusName: { type: `string`, sql: `status_name`, title: '任務狀態' },
        sortOrder: { type: `number`, sql: `status_sort`, title: '狀態排序 (Hidden)' },
        diffVxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' },
        diffRegion: { type: `string`, sql: `region`, title: '地區' },
        diffPlant: { type: `string`, sql: `plant`, title: '廠區' },
        diffFactory: { type: `string`, sql: `factory`, title: '工廠' },
        diffLine: { type: `string`, sql: `line`, title: '線體' }
    }
});
