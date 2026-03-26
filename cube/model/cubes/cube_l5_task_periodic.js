/**
 * L5 任務完成率 Cube - 標準版 (Updated 2026-03-26)
 * 
 * 核心邏輯: 採用 Time Machine 架構，支援回溯查詢。
 * 資料來源: 連結至 ClickHouse Gold Layer 視圖 (gold.rmv_l5_task_completion)。
 * 備註: 查詢對象為 View 而非 Table，以確保 ReplacingMergeTree 的資料在讀取時透過 FINAL 取得最新版本。
 */
cube(`L5TaskPeriodic`, {
    sql: `
    WITH 
        params AS (
            SELECT 
                max(snapshot_date) as max_filtered_date,
                today() as sys_today
            FROM gold.rmv_l5_task_completion -- 對接 Gold層 視圖 (View) 以確保資料完全聚合

            WHERE (
                ${FILTER_PARAMS.L5TaskPeriodic.snapshotDate.filter('toString(snapshot_date)')}
                OR ${FILTER_PARAMS.L5TaskPeriodic.snapshotDate.filter("formatDateTime(snapshot_date, '%Y-%m-%d 00:00:00.000000')")}
                OR ${FILTER_PARAMS.L5TaskPeriodic.snapshotDate.filter("formatDateTime(snapshot_date, '%Y-%m-%dT00:00:00.000Z')")}
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
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffVxType.filter('vx_type')}
        )

    -- A. Month: 加總當月所有任務，但 Acc 只取月底快照
    SELECT 'Month' as granularity, formatDateTime(anchor_dt, '%b.') as period_name, 1 as sort_order,
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

    -- B. Week: 加總當週所有任務，但 Acc 只取週日快照
    SELECT 'Week' as granularity, concat('W', toString(toWeek(snapshot_date, 1))) as period_name,
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

    -- C. Day: 當日任務，但 Acc 使用 7 天滾動總量作為分母
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

    UNION ALL

    -- D. 專門給過濾器下拉選單看的資料 (Filter List Exposure)
    SELECT 
        'FilterRef' as granularity,
        '' as period_name,
        99 as sort_order,
        '' as vx_type, '' as region, '' as plant, '' as factory, '' as line,
        snapshot_date as filter_date,
        snapshot_date as snapshot_date_real,
        0 as total_qty, 0 as todo_qty, 0 as doing_qty,
        0 as doing_done_qty, 0 as done_qty, 0 as acc_qty,
        0 as acc_total_qty
    FROM (SELECT DISTINCT snapshot_date FROM gold.rmv_l5_task_completion)
    `,

    measures: {
        totalQty: { type: `sum`, sql: `total_qty`, title: 'QTY: Total' },
        todoQty: { type: `sum`, sql: `todo_qty`, title: 'QTY: Todo' },
        doingQty: { type: `sum`, sql: `doing_qty`, title: 'QTY: Doing' },
        doneQty: { type: `sum`, sql: `done_qty`, title: 'QTY: Done' },
        doingDoneQty: { type: `sum`, sql: `doing_done_qty`, title: 'QTY: Doing+Done' },
        accQty: { type: `sum`, sql: `acc_qty`, title: 'QTY: Todo+Doing(Acc)' },

        doneRate: { type: `number`, sql: `round(sum(done_qty) * 100.0 / nullIf(sum(total_qty), 0), 2)`, title: 'Rate: Done' },
        doingDoneRate: { type: `number`, sql: `round(sum(doing_done_qty) * 100.0 / nullIf(sum(total_qty), 0), 2)`, title: 'Rate: Doing+Done' },
        accRate: { type: `number`, sql: `round(sum(acc_qty) * 100.0 / nullIf(sum(acc_total_qty), 0), 2)`, title: 'Rate: Acc (Todo+Doing)' },

        periodSortOrder: { type: `max`, sql: `sort_order`, title: '排序用(Hidden)' }
    },

    dimensions: {
        periodName: { type: `string`, sql: `period_name`, title: '週期/日期' },
        // 將 type 改為 string 並格式化，避免 Superset 帶入 T00:00:00.000Z 導致 ClickHouse Date 轉換失敗
        snapshotDate: {
            type: `string`,
            sql: `formatDateTime(filter_date, '%Y-%m-%d')`,
            title: '日期篩選(決定 Anchor)'
        },
        realSnapshotDate: { type: `time`, sql: `snapshot_date_real`, title: '實際資料日期' },

        // 五階組織維度
        diffVxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' },
        diffRegion: { type: `string`, sql: `region`, title: '地區' },
        diffPlant: { type: `string`, sql: `plant`, title: '廠區' },
        diffFactory: { type: `string`, sql: `factory`, title: '工廠' },
        diffLine: { type: `string`, sql: `line`, title: '線體' }
    }
});