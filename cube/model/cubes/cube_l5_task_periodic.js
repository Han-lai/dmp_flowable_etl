/**
 * L5 任務完成率 Cube - 標準版 (V4.2 同梯次 Cohort 版)
 * 目的：提供高階 KPI 指標，支持「7天日趨勢 + 3週對比 + 當月累計」的單一視圖。
 * 特色：
 * 1. 週期感知 (Period-Aware)：自動根據開單日判定結算狀態。
 * 2. 同梯次 (Cohort)：確保 TODO + DOING + DONE = TOTAL，數據互斥且不重複。
 * 3. 時光機模式：透過 ca.anchor_dt 鎖定基準日，確保 Filter 不會濾除回溯所需的歷史分片。
 */
cube(`L5TaskPeriodic`, {
    sql: `
    WITH
        -- [1] 參數提取：獲取使用者篩選的基準日期 (通常是最新的一天)
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
        -- [2] 錨點計算：確保基準日不超過今天，作為所有時間區間回溯的起點
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
        anchor_dt as filter_date, -- 用於維度篩選的邏輯日期
        total_task,               -- 原始 Bitmap 欄位
        todo,                     -- 對應粒度的結算 Bitmap
        doing,
        done,
        acc,
        acc_total_task             -- 新增：7日滾動總量
    FROM (
        -- 1. Day 粒度 (回溯 7 天)：展現最近一週的日趨勢
        SELECT
            vx_type, region, plant, factory, line, snapshot_date,
            toString(snapshot_date) as period_name, 'Day' as granularity,
            5 + dateDiff('day', snapshot_date, ca.anchor_dt) as sort_order,
            ca.anchor_dt as anchor_dt,
            total_task, todo_daily as todo, doing_daily as doing, done_daily as done, acc, acc_total_task
        FROM gold.rmv_l5_task_completion_phys
        CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN (ca.anchor_dt - INTERVAL 6 DAY) AND ca.anchor_dt

        UNION ALL

        -- 2a. Week 粒度 (Wx - 當前 ISO 週)：展現本週累計績效
        SELECT vx_type, region, plant, factory, line, snapshot_date,
               concat('W', toString(toISOWeek(ca.anchor_dt))) as period_name, 'Week' as granularity,
               2 as sort_order,
               ca.anchor_dt as anchor_dt,
               total_task, todo_weekly as todo, doing_weekly as doing, done_weekly as done, acc, acc_total_task
        FROM gold.rmv_l5_task_completion_phys CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN toStartOfWeek(ca.anchor_dt, 3) AND toStartOfWeek(ca.anchor_dt, 3) + INTERVAL 6 DAY

        UNION ALL

        -- 2b. Week 粒度 (Wx-1 - 前一週)
        SELECT vx_type, region, plant, factory, line, snapshot_date,
               concat('W', toString(toISOWeek(ca.anchor_dt - INTERVAL 7 DAY))) as period_name, 'Week' as granularity,
               3 as sort_order,
               ca.anchor_dt as anchor_dt,
               total_task, todo_weekly as todo, doing_weekly as doing, done_weekly as done, acc, acc_total_task
        FROM gold.rmv_l5_task_completion_phys CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN toStartOfWeek(ca.anchor_dt - INTERVAL 7 DAY, 3)
                                AND toStartOfWeek(ca.anchor_dt - INTERVAL 7 DAY, 3) + INTERVAL 6 DAY

        UNION ALL

        -- 2c. Week 粒度 (Wx-2 - 前兩週)
        SELECT vx_type, region, plant, factory, line, snapshot_date,
               concat('W', toString(toISOWeek(ca.anchor_dt - INTERVAL 14 DAY))) as period_name, 'Week' as granularity,
               4 as sort_order,
               ca.anchor_dt as anchor_dt,
               total_task, todo_weekly as todo, doing_weekly as doing, done_weekly as done, acc, acc_total_task
        FROM gold.rmv_l5_task_completion_phys CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN toStartOfWeek(ca.anchor_dt - INTERVAL 14 DAY, 3)
                                AND toStartOfWeek(ca.anchor_dt - INTERVAL 14 DAY, 3) + INTERVAL 6 DAY

        UNION ALL

        -- 3. Month 粒度 (MMM - 當前月)：展現當月累積進度
        SELECT vx_type, region, plant, factory, line, snapshot_date,
               formatDateTime(ca.anchor_dt, '%b.') as period_name, 'Month' as granularity,
               1 as sort_order,
               ca.anchor_dt as anchor_dt,
               total_task, todo_monthly as todo, doing_monthly as doing, done_monthly as done, acc, acc_total_task
        FROM gold.rmv_l5_task_completion_phys CROSS JOIN calc_anchor AS ca
        WHERE snapshot_date BETWEEN toStartOfMonth(ca.anchor_dt) AND toLastDayOfMonth(ca.anchor_dt)
    )
    `,

    measures: {
        // [數量指標]：使用 groupBitmapMergeState 將多行 Bitmap 進行聯集，再計算基數 (Cardinality)
        totalQty: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(total_task))`,
            title: 'QTY: Total'
        },
        todoQty: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(todo))`,
            title: 'QTY: Todo'
        },
        doingQty: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(doing))`,
            title: 'QTY: Doing'
        },
        doneQty: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(done))`,
            title: 'QTY: Done'
        },
        // [複合指標]：Doing + Done 聯集
        doingDoneQty: {
            type: `number`,
            sql: `bitmapCardinality(bitmapOr(groupBitmapMergeState(doing), groupBitmapMergeState(done)))`,
            title: 'QTY: Doing+Done'
        },
        accQty: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(acc))`,
            title: 'QTY: Todo+Doing(Acc)'
        },
        accTotalQty: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(acc_total_task))`,
            title: 'QTY: Acc Total'
        },
        effectiveDenominator: {
            type: `number`,
            sql: `bitmapCardinality(groupBitmapMergeState(total_task))`,
            title: 'Denominator'
        },
        // [達成率指標]
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
            sql: `
            CASE
                WHEN any(granularity) = 'Day' THEN round(${accQty} * 100.0 / nullIf(${accTotalQty}, 0), 2)
                ELSE round((${todoQty} + ${doingQty}) * 100.0 / nullIf(${totalQty}, 0), 2)
            END`,
            title: 'Rate: Acc (積壓/落後率)'
        },

        periodSortOrder: { type: `max`, sql: `sort_order`, title: '排序用(Hidden)' }
    },

    dimensions: {
        // [時間維度]
        periodName: { type: `string`, sql: `period_name`, title: '週期/日期名' },
        snapshotDate: { type: `string`, sql: `filter_date`, title: '日期篩選(基準日期)' },
        realSnapshotDate: { type: `string`, sql: `formatDateTime(snapshot_date, '%Y-%m-%d')`, title: '實際快照日期' },
        granularity: { type: `string`, sql: `granularity`, title: '粒度' },

        // [製造維度]
        diffVxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' },
        diffRegion: { type: `string`, sql: `region`, title: '地區' },
        diffPlant: { type: `string`, sql: `plant`, title: '廠區' },
        diffFactory: { type: `string`, sql: `factory`, title: '工廠' },
        diffLine: { type: `string`, sql: `line`, title: '線體' }
    }
});