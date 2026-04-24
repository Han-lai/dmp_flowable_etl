/**
 * L5 任務完成率 Cube - 標準版 (V3.2 穩定版)
 * 修正: 確保 filter_date (snapshotDate) 指向 anchor_dt，解決 Superset 篩選時吞掉歷史資料的問題。
 */
cube(`L5TaskPeriodic`, {
    sql: `
    WITH
        params AS (
            SELECT
                max(snapshot_date) as max_filtered_date,
                today() as sys_today
            FROM gold.rmv_l5_task_completion_phys
            WHERE (
                ${FILTER_PARAMS.L5TaskPeriodic.snapshotDate.filter("formatDateTime(snapshot_date, '%Y-%m-%d')")}
            )
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffVxType.filter('vx_type')}
        ),
        calc_anchor AS (
            SELECT
                CASE
                    WHEN max_filtered_date >= sys_today THEN sys_today
                    ELSE max_filtered_date
                END as anchor_dt
            FROM params
        )

    SELECT
        vx_type, region, plant, factory, line,
        snapshot_date,
        period_name,
        granularity,
        sort_order,
        anchor_dt as filter_date,
        total_task,
        todo,
        doing,
        done,
        acc
    FROM (
        -- 1. Day (回溯 7 天)
        SELECT
            vx_type, region, plant, factory, line, snapshot_date,
            toString(snapshot_date) as period_name, 'Day' as granularity,
            5 + dateDiff('day', snapshot_date, ca.anchor_dt) as sort_order,
            ca.anchor_dt as anchor_dt,
            total_task, todo, doing, done, acc
        FROM gold.rmv_l5_task_completion_phys
        CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN (ca.anchor_dt - INTERVAL 6 DAY) AND ca.anchor_dt

        UNION ALL

        -- 2a. Week (Wx - 當前週: 從週一到 anchor_dt)
        SELECT vx_type, region, plant, factory, line, snapshot_date,
               concat('W', toString(toISOWeek(ca.anchor_dt))) as period_name, 'Week' as granularity,
               2 as sort_order,
               ca.anchor_dt as anchor_dt,
               total_task, todo, doing, done, acc
        FROM gold.rmv_l5_task_completion_phys CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN toStartOfWeek(ca.anchor_dt, 3) AND ca.anchor_dt

        UNION ALL

        -- 2b. Week (Wx-1 - 前一週)
        SELECT vx_type, region, plant, factory, line, snapshot_date,
               concat('W', toString(toISOWeek(ca.anchor_dt - INTERVAL 7 DAY))) as period_name, 'Week' as granularity,
               3 as sort_order,
               ca.anchor_dt as anchor_dt,
               total_task, todo, doing, done, acc
        FROM gold.rmv_l5_task_completion_phys CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN toStartOfWeek(ca.anchor_dt - INTERVAL 7 DAY, 3)
                                AND toStartOfWeek(ca.anchor_dt - INTERVAL 7 DAY, 3) + INTERVAL 6 DAY

        UNION ALL

        -- 2c. Week (Wx-2 - 前兩週)
        SELECT vx_type, region, plant, factory, line, snapshot_date,
               concat('W', toString(toISOWeek(ca.anchor_dt - INTERVAL 14 DAY))) as period_name, 'Week' as granularity,
               4 as sort_order,
               ca.anchor_dt as anchor_dt,
               total_task, todo, doing, done, acc
        FROM gold.rmv_l5_task_completion_phys CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN toStartOfWeek(ca.anchor_dt - INTERVAL 14 DAY, 3)
                                AND toStartOfWeek(ca.anchor_dt - INTERVAL 14 DAY, 3) + INTERVAL 6 DAY

        UNION ALL

        -- 3. Month (MMM - 當前月)
        SELECT vx_type, region, plant, factory, line, snapshot_date,
               formatDateTime(ca.anchor_dt, '%b.') as period_name, 'Month' as granularity,
               1 as sort_order,
               ca.anchor_dt as anchor_dt,
               total_task, todo, doing, done, acc
        FROM gold.rmv_l5_task_completion_phys CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN toStartOfMonth(ca.anchor_dt) AND ca.anchor_dt
    )
    `,

    measures: {
        totalQty: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(total_task))`,
            title: 'QTY: Total'
        },
        todoQty: {
            type: `number`,
            sql: `bitmapCardinality(bitmapAndnot(groupBitmapMergeState(todo), bitmapOr(groupBitmapMergeState(doing), groupBitmapMergeState(done))))`,
            title: 'QTY: Todo'
        },
        doingQty: {
            type: `number`,
            sql: `bitmapCardinality(bitmapAndnot(groupBitmapMergeState(doing), groupBitmapMergeState(done)))`,
            title: 'QTY: Doing'
        },
        doneQty: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(done))`,
            title: 'QTY: Done'
        },
        doingDoneQty: {
            type: `number`,
            sql: `bitmapCardinality(bitmapOr(groupBitmapMergeState(doing), groupBitmapMergeState(done)))`,
            title: 'QTY: Doing+Done'
        },
        accQty: {
            type: `number`,
            sql: `
                CASE 
                    WHEN min(granularity) = 'Day' THEN bitmapCardinality(groupBitmapMergeState(acc))
                    ELSE bitmapCardinality(
                        bitmapAndnot(
                            bitmapOr(groupBitmapMergeState(todo), groupBitmapMergeState(doing)),
                            groupBitmapMergeState(done)
                        )
                    )
                END
            `,
            title: 'QTY: Todo+Doing(Acc)'
        },
        effectiveDenominator: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(total_task))`,
            title: 'Denominator'
        },
        doneRate: {
            type: `number`,
            sql: `round(${doneQty} * 100.0 / nullIf(${effectiveDenominator}, 0), 2)`,
            title: 'Rate: Done'
        },
        doingDoneRate: {
            type: `number`,
            sql: `round(${doingDoneQty} * 100.0 / nullIf(${effectiveDenominator}, 0), 2)`,
            title: 'Rate: Doing+Done'
        },
        accRate: {
            type: `number`,
            sql: `round(${accQty} * 100.0 / nullIf(${effectiveDenominator}, 0), 2)`,
            title: 'Rate: Acc (Todo+Doing)'
        },
        periodSortOrder: { type: `max`, sql: `sort_order`, title: '排序用(Hidden)' }
    },

    dimensions: {
        periodName: { type: `string`, sql: `period_name`, title: '週期/日期名' },
        snapshotDate: { type: `string`, sql: `filter_date`, title: '日期篩選(基準日期)' },
        realSnapshotDate: { type: `string`, sql: `formatDateTime(snapshot_date, '%Y-%m-%d')`, title: '實際快照日期' },
        granularity: { type: `string`, sql: `granularity`, title: '粒度' },

        diffVxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' },
        diffRegion: { type: `string`, sql: `region`, title: '地區' },
        diffPlant: { type: `string`, sql: `plant`, title: '廠區' },
        diffFactory: { type: `string`, sql: `factory`, title: '工廠' },
        diffLine: { type: `string`, sql: `line`, title: '線體' }
    }
});