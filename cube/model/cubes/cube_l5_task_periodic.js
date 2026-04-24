/**
 * L5 任務完成率 Cube - 標準版 (V3.2 穩定版)
 * 基準定義:
 * 1. 指標順序: Total > Todo > Doing > Done > Doing+Done > Acc
 * 2. 指標邏輯: 存量指標以「週期最後一日」為基準 (Stock Snapshot)
 * 3. 分母邏輯: 所有粒度統一使用 total_task (7D Rolling 分母已移至 ETL 層計算)
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
                ${FILTER_PARAMS.L5TaskPeriodic.snapshotDate.filter('snapshot_date')}
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

        -- 2a. Week (Wx - 當前週: 從週一到 anchor_dt 的所有快照累積)
        -- 使用 BETWEEN 確保即使 anchor_dt 當天無快照也能取到本週資料
        SELECT vx_type, region, plant, factory, line, snapshot_date,
               concat('W', toString(toISOWeek(ca.anchor_dt))) as period_name, 'Week' as granularity,
               2 as sort_order,
               ca.anchor_dt as anchor_dt,
               total_task, todo, doing, done, acc
        FROM gold.rmv_l5_task_completion_phys CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN toStartOfWeek(ca.anchor_dt, 3) AND ca.anchor_dt

        UNION ALL

        -- 2b. Week (Wx-1 - 前一週: 該週所有快照累積)
        SELECT vx_type, region, plant, factory, line, snapshot_date,
               concat('W', toString(toISOWeek(ca.anchor_dt - INTERVAL 7 DAY))) as period_name, 'Week' as granularity,
               3 as sort_order,
               ca.anchor_dt as anchor_dt,
               total_task, todo, doing, done, acc
        FROM gold.rmv_l5_task_completion_phys CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN toStartOfWeek(ca.anchor_dt - INTERVAL 7 DAY, 3)
                                AND toStartOfWeek(ca.anchor_dt - INTERVAL 7 DAY, 3) + INTERVAL 6 DAY

        UNION ALL

        -- 2c. Week (Wx-2 - 前兩週: 該週所有快照累積)
        SELECT vx_type, region, plant, factory, line, snapshot_date,
               concat('W', toString(toISOWeek(ca.anchor_dt - INTERVAL 14 DAY))) as period_name, 'Week' as granularity,
               4 as sort_order,
               ca.anchor_dt as anchor_dt,
               total_task, todo, doing, done, acc
        FROM gold.rmv_l5_task_completion_phys CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN toStartOfWeek(ca.anchor_dt - INTERVAL 14 DAY, 3)
                                AND toStartOfWeek(ca.anchor_dt - INTERVAL 14 DAY, 3) + INTERVAL 6 DAY

        UNION ALL

        -- 3. Month (MMM - 當前月: 從月初到 anchor_dt 的所有快照累積)
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
        // 1. Total Task
        totalQty: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(total_task))`,
            title: 'QTY: Total'
        },

        // 2. Todo (Snapshot)
        todoQty: {
            type: `number`,
            sql: `bitmapCardinality(bitmapAndnot(groupBitmapMergeState(todo), bitmapOr(groupBitmapMergeState(doing), groupBitmapMergeState(done))))`,
            title: 'QTY: Todo'
        },

        // 3. Doing (Snapshot)
        doingQty: {
            type: `number`,
            sql: `bitmapCardinality(bitmapAndnot(groupBitmapMergeState(doing), groupBitmapMergeState(done)))`,
            title: 'QTY: Doing'
        },

        // 4. Done (Snapshot)
        doneQty: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(done))`,
            title: 'QTY: Done'
        },

        // 5. Doing + Done
        doingDoneQty: {
            type: `number`,
            sql: `bitmapCardinality(bitmapOr(groupBitmapMergeState(doing), groupBitmapMergeState(done)))`,
            title: 'QTY: Doing+Done'
        },

        // 6. Todo + Doing (Acc) - 雙軌邏輯對齊
        // 日別: 讀取 7D Rolling 位圖
        // 週/月: 執行「先週期聯集、後排他過濾」(Union(A) - Union(B))
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

        // 分母指標: 統一使用 total_task
        // (7D Rolling 分母的計算已移至 ETL 層，Cube 層暫統一使用快照總量)
        effectiveDenominator: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(total_task))`,
            title: 'Denominator'
        },

        // Ratios
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
        periodName: { type: `string`, sql: `period_name`, title: '週期/日期' },
        snapshotDate: { type: `time`, sql: `filter_date`, title: '日期篩選(決定 Anchor)' },
        realSnapshotDate: { type: `time`, sql: `snapshot_date`, title: '實際資料日期' },
        granularity: { type: `string`, sql: `granularity`, title: '粒度' },

        diffVxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' },
        diffRegion: { type: `string`, sql: `region`, title: '地區' },
        diffPlant: { type: `string`, sql: `plant`, title: '廠區' },
        diffFactory: { type: `string`, sql: `factory`, title: '工廠' },
        diffLine: { type: `string`, sql: `line`, title: '線體' }
    }
});