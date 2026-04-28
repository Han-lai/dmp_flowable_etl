/**
 * L5 任務完成率 Cube - Pivot 版 (V4.2 同梯次 Cohort 版)
 * 
 * 修正: 
 * 1. 確保 filter_date (snapshotDate) 在所有 UNION 分支中都指向 anchor_dt，避免篩選時過濾掉歷史資料。
 * 2. Day 粒度調整為回溯 7 天 (INTERVAL 6 DAY)。
 * 3. V4 邏輯下，Todo/Doing/Done 為互斥狀態，不需要使用複雜的 bitmapAndnot 進行排他計算。
 */

cube(`L5TaskPeriodicPivot`, {
    sql: `
    WITH 
        params AS (
            SELECT 
                max(snapshot_date) as max_filtered_date,
                today() as sys_today
            FROM gold.rmv_l5_task_completion_phys
            WHERE (
                ${FILTER_PARAMS.L5TaskPeriodicPivot.snapshotDate.filter("formatDateTime(snapshot_date, '%Y-%m-%d')")}
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
            FROM gold.rmv_l5_task_completion_phys
            CROSS JOIN calc_anchor
            WHERE snapshot_date >= toStartOfMonth(anchor_dt) - INTERVAL 1 MONTH
              AND snapshot_date <= toLastDayOfMonth(anchor_dt) + INTERVAL 1 MONTH
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffVxType.filter('vx_type')}
        ),

        v4_wide_metrics AS (
            -- A. Month: 當月累積
            SELECT 
                'Month' as granularity, formatDateTime(anchor_dt, '%b.') as period_name, 1 as sort_order,
                vx_type, region, plant, factory, line, 
                formatDateTime(anchor_dt, '%Y-%m-%d') as filter_date, formatDateTime(anchor_dt, '%Y-%m-%d') as snapshot_date_real,
                bitmapCardinality(groupBitmapMergeState(total_task)) as total_qty, 
                bitmapCardinality(groupBitmapMergeState(todo_monthly)) as todo_qty, 
                bitmapCardinality(groupBitmapMergeState(doing_monthly)) as doing_qty,
                bitmapCardinality(bitmapOr(groupBitmapMergeState(doing_monthly), groupBitmapMergeState(done_monthly))) as doing_done_qty, 
                bitmapCardinality(groupBitmapMergeState(done_monthly)) as done_qty, 
                bitmapCardinality(groupBitmapMergeState(acc)) as acc_qty,
                bitmapCardinality(groupBitmapMergeState(total_task)) as acc_total_qty
            FROM base
            WHERE snapshot_date >= toStartOfMonth(anchor_dt) AND snapshot_date <= anchor_dt
            GROUP BY vx_type, region, plant, factory, line, anchor_dt, period_name

            UNION ALL

            -- B. Week: 包含當週與前兩週 (共三週)
            SELECT 
                'Week' as granularity, concat('W', toString(toISOWeek(snapshot_date))) as period_name,
                CASE WHEN toISOWeek(snapshot_date) = toISOWeek(anchor_dt) THEN 2
                     WHEN toISOWeek(snapshot_date) = toISOWeek(anchor_dt - INTERVAL 7 DAY) THEN 3
                     ELSE 4 END as sort_order,
                vx_type, region, plant, factory, line,
                formatDateTime(anchor_dt, '%Y-%m-%d') as filter_date, max(formatDateTime(snapshot_date, '%Y-%m-%d')) as snapshot_date_real,
                bitmapCardinality(groupBitmapMergeState(total_task)) as total_qty, 
                bitmapCardinality(groupBitmapMergeState(todo_weekly)) as todo_qty, 
                bitmapCardinality(groupBitmapMergeState(doing_weekly)) as doing_qty,
                bitmapCardinality(bitmapOr(groupBitmapMergeState(doing_weekly), groupBitmapMergeState(done_weekly))) as doing_done_qty, 
                bitmapCardinality(groupBitmapMergeState(done_weekly)) as done_qty, 
                bitmapCardinality(groupBitmapMergeState(acc)) as acc_qty,
                bitmapCardinality(groupBitmapMergeState(total_task)) as acc_total_qty
            FROM base
            WHERE (
                (toISOWeek(snapshot_date) = toISOWeek(anchor_dt) AND snapshot_date <= anchor_dt) OR 
                (toISOWeek(snapshot_date) = toISOWeek(anchor_dt - INTERVAL 7 DAY)) OR
                (toISOWeek(snapshot_date) = toISOWeek(anchor_dt - INTERVAL 14 DAY))
            )
            GROUP BY granularity, period_name, sort_order, vx_type, region, plant, factory, line, anchor_dt

            UNION ALL

            -- C. Day: 前 7 天數值
            SELECT 
                'Day' as granularity, toString(snapshot_date) as period_name,
                5 + dateDiff('day', snapshot_date, anchor_dt) as sort_order,
                vx_type, region, plant, factory, line,
                formatDateTime(anchor_dt, '%Y-%m-%d') as filter_date, formatDateTime(snapshot_date, '%Y-%m-%d') as snapshot_date_real,
                bitmapCardinality(groupBitmapMergeState(total_task)) as total_qty, 
                bitmapCardinality(groupBitmapMergeState(todo_daily)) as todo_qty, 
                bitmapCardinality(groupBitmapMergeState(doing_daily)) as doing_qty,
                bitmapCardinality(bitmapOr(groupBitmapMergeState(doing_daily), groupBitmapMergeState(done_daily))) as doing_done_qty, 
                bitmapCardinality(groupBitmapMergeState(done_daily)) as done_qty, 
                bitmapCardinality(groupBitmapMergeState(acc)) as acc_qty,
                bitmapCardinality(groupBitmapMergeState(total_task)) as acc_total_qty
            FROM base
            WHERE snapshot_date BETWEEN (anchor_dt - INTERVAL 6 DAY) AND anchor_dt
            GROUP BY granularity, period_name, sort_order, vx_type, region, plant, factory, line, anchor_dt, snapshot_date
        )

    SELECT * FROM (
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '1. Total Task' as status_name, total_qty as task_qty, 100.0 as task_pct, 1 as status_sort FROM v4_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '2. Todo' as status_name, todo_qty as task_qty, round(todo_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 2 as status_sort FROM v4_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '3. Doing' as status_name, doing_qty as task_qty, round(doing_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 3 as status_sort FROM v4_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '4. Done' as status_name, done_qty as task_qty, round(done_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 4 as status_sort FROM v4_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '5. Doing+Done' as status_name, doing_done_qty as task_qty, round(doing_done_qty * 100.0 / nullIf(total_qty, 0), 2) as task_pct, 5 as status_sort FROM v4_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '6. Todo+Doing(Acc)' as status_name, acc_qty as task_qty, round(acc_qty * 100.0 / nullIf(acc_total_qty, 0), 2) as task_pct, 6 as status_sort FROM v4_wide_metrics
    ) AS pivoted_result
    `,

    title: 'L5 任務完成率 (Pivot)',
    description: 'V4 同梯次 Cohort 版 Pivot 視圖，指標已簡化互斥。',

    measures: {
        taskQty: { type: `sum`, sql: `task_qty`, title: 'Task Qty' },
        taskPct: { type: `avg`, sql: `task_pct`, title: 'Task (%)' },
        periodSortOrder: { type: `max`, sql: `period_sort`, title: 'Period Sort (Hidden)' }
    },

    dimensions: {
        id: { sql: `concat(toString(snapshot_date_real), '_', region, '_', plant, '_', factory, '_', line, '_', vx_type, '_', status_name, '_', period_name)`, type: `string`, primaryKey: true },
        snapshotDate: { type: `string`, sql: `filter_date`, title: '日期篩選(基準日期)' },
        realSnapshotDate: { type: `string`, sql: `snapshot_date_real`, title: '實際快照日期' },
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
