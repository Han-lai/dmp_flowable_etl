/**
 * L5 任務完成率 Cube - Pivot 版 (V4.2 同梯次 Cohort 版)
 * 目的：將 TODO, DOING, DONE 等多個指標從「欄位 (Measures)」轉換為「列 (Status Name)」。
 * 商業意義：方便前端表格直接呈現狀態對比，支持單一圖表顯示所有狀態的百分比。
 * 
 * [Changelog]
 * - 2026-05-26: 
 *   1. [架構大躍進 - 方案C] 捨棄即時的 Bitmap 運算，改為讀取 ETL 預聚合的整數彙總表 (gold.rmv_l5_task_summary)。
 *   2. [寬表優化] 直接從預聚合表選取所需欄位，不再需要透過 CROSS JOIN 與繁重的 bitmap 運算去兜出寬表，效能極大幅提升。
 */

cube(`L5TaskPeriodicPivot`, {
    sql: `
    WITH 
        -- [1] 參數提取：鎖定使用者選擇的基準日
        (
            SELECT 
                CASE 
                    WHEN max(snapshot_date) >= today() THEN today() 
                    ELSE max(snapshot_date)
                END
            FROM gold.rmv_l5_task_summary FINAL
            WHERE period_type = 'Day'
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.snapshotDate.filter("snapshot_date")}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffVxType.filter('vx_type')}
        ) AS anchor_dt,

        -- [3] 指標展平 (Wide Format)：從預聚合表讀取
        v4_wide_metrics AS (
            -- A. Month: 當月累積
            SELECT 
                'Month' as granularity, period_name, 1 as sort_order,
                vx_type, region, plant, factory, line, 
                anchor_dt as filter_date, snapshot_date as snapshot_date_real,
                total_qty, todo_qty, doing_qty, doing_done_qty, done_qty, acc_qty, acc_total_qty
            FROM gold.rmv_l5_task_summary FINAL
            WHERE period_type = 'Month'
              AND period_key = formatDateTime(anchor_dt, '%Y-%m')
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffVxType.filter('vx_type')}

            UNION ALL

            -- B. Week: 本週與前兩週
            SELECT 
                'Week' as granularity, period_name,
                CASE WHEN period_key = concat(toString(toISOYear(anchor_dt)), '-W', lpad(toString(toISOWeek(anchor_dt)), 2, '0')) THEN 2
                     WHEN period_key = concat(toString(toISOYear(anchor_dt - INTERVAL 7 DAY)), '-W', lpad(toString(toISOWeek(anchor_dt - INTERVAL 7 DAY)), 2, '0')) THEN 3
                     ELSE 4 END as sort_order,
                vx_type, region, plant, factory, line,
                anchor_dt as filter_date, snapshot_date as snapshot_date_real,
                total_qty, todo_qty, doing_qty, doing_done_qty, done_qty, acc_qty, acc_total_qty
            FROM gold.rmv_l5_task_summary FINAL
            WHERE period_type = 'Week'
              AND (
                  period_key = concat(toString(toISOYear(anchor_dt)), '-W', lpad(toString(toISOWeek(anchor_dt)), 2, '0')) OR
                  period_key = concat(toString(toISOYear(anchor_dt - INTERVAL 7 DAY)), '-W', lpad(toString(toISOWeek(anchor_dt - INTERVAL 7 DAY)), 2, '0')) OR
                  period_key = concat(toString(toISOYear(anchor_dt - INTERVAL 14 DAY)), '-W', lpad(toString(toISOWeek(anchor_dt - INTERVAL 14 DAY)), 2, '0'))
              )
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffVxType.filter('vx_type')}

            UNION ALL

            -- C. Day: 前 7 天趨勢
            SELECT 
                'Day' as granularity, period_name,
                5 + dateDiff('day', snapshot_date, anchor_dt) as sort_order,
                vx_type, region, plant, factory, line,
                anchor_dt as filter_date, snapshot_date as snapshot_date_real,
                total_qty, todo_qty, doing_qty, doing_done_qty, done_qty, acc_qty, acc_total_qty
            FROM gold.rmv_l5_task_summary FINAL
            WHERE period_type = 'Day'
              AND snapshot_date BETWEEN (anchor_dt - INTERVAL 6 DAY) AND anchor_dt
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodicPivot.diffVxType.filter('vx_type')}
        )

    -- [4] 數據轉置 (Pivot)：將寬表轉為窄表 (Long Format)
    SELECT * FROM (
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '1. Total Task' as status_name, total_qty as task_qty, 100.0 as task_pct, 1 as status_sort FROM v4_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '2. Todo' as status_name, todo_qty as task_qty, floor(todo_qty * 100.0 / nullIf(total_qty, 0)) as task_pct, 2 as status_sort FROM v4_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '3. Doing' as status_name, doing_qty as task_qty, floor(doing_qty * 100.0 / nullIf(total_qty, 0)) as task_pct, 3 as status_sort FROM v4_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '4. Done' as status_name, done_qty as task_qty, if(done_qty >= total_qty, 100, floor(done_qty * 100.0 / nullIf(total_qty, 0))) as task_pct, 4 as status_sort FROM v4_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '5. Doing+Done' as status_name, doing_done_qty as task_qty, if(doing_done_qty >= total_qty, 100, floor(doing_done_qty * 100.0 / nullIf(total_qty, 0))) as task_pct, 5 as status_sort FROM v4_wide_metrics
        UNION ALL
        SELECT vx_type, region, plant, factory, line, filter_date, snapshot_date_real, granularity, period_name, sort_order as period_sort,
            '6. Todo+Doing(Acc)' as status_name, acc_qty as task_qty, if(acc_qty >= acc_total_qty, 100, floor(acc_qty * 100.0 / nullIf(acc_total_qty, 0))) as task_pct, 6 as status_sort FROM v4_wide_metrics
    ) AS pivoted_result
    `,

    title: 'L5 任務完成率 (Pivot)',
    description: 'V4 同梯次 Cohort 版 Pivot 視圖，支持狀態列展示。',

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
        statusName: { type: `string`, sql: `status_name`, title: '任務狀態', description: 'TODO, DOING, DONE 等結算狀態名稱' },
        sortOrder: { type: `number`, sql: `status_sort`, title: '狀態排序 (Hidden)' },
        
        // [製造維度項]
        diffVxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' },
        diffRegion: { type: `string`, sql: `region`, title: '地區' },
        diffPlant: { type: `string`, sql: `plant`, title: '廠區' },
        diffFactory: { type: `string`, sql: `factory`, title: '工廠' },
        diffLine: { type: `string`, sql: `line`, title: '線體' }
    }
});
