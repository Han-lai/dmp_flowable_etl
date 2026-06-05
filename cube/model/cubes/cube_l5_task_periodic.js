/**
 * L5 任務完成率 Cube (V4.3 預聚合版)
 * 目的：提供高階 KPI 指標，支持「7天日趨勢 + 3週對比 + 當月累計」的單一視圖。
 *
 * [Changelog]
 * - 2026-05-27 (V4.3):
 *   捨棄即時 Bitmap 運算，改讀 ETL 預聚合整數彙總表 (gold.rmv_l5_task_summary)。
 *   Measures 從 groupBitmapMerge 改為 SUM，SQL 層從讀取 Bitmap 欄位改為讀取整數欄位。
 *   accQty 在 Week/Month 粒度改用同梯次積壓 (Todo + Doing) 邏輯，由 ETL 階段計算後寫入。
 * - 2026-06-05 (V4.4):
 *   新增 todoRate / doingRate measures，使用 floor() 計算符合 Rule 2 規格
 *   （原本由 BFF reports.js calcRate() 以 Math.round() 計算，不符合無條件捨去規格）。
 *   doneRate / doingDoneRate / accRate 同步從 round() 改為 floor()，統一符合 Rule 2。
 * - 2026-05-25 (V4.2):
 *   將 params CTE 重構為 Constant Scalar WITH，移除 CROSS JOIN calc_anchor。
 *   所有 Bitmap 數量指標從 bitmapCardinality(groupBitmapMergeState(x)) 改為 groupBitmapMerge(x)。
 *   移除 snapshotDate 篩選器上的 formatDateTime() 包裝，修復主鍵索引命中問題。
 */
cube(`L5TaskPeriodic`, {
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
              AND ${FILTER_PARAMS.L5TaskPeriodic.snapshotDate.filter("snapshot_date")}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffRegion.filter('region')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffPlant.filter('plant')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffFactory.filter('factory')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffLine.filter('line')}
              AND ${FILTER_PARAMS.L5TaskPeriodic.diffVxType.filter('vx_type')}
        ) AS anchor_dt

    SELECT * FROM (
        -- A. Month: 當月累積
        SELECT
            'Month' as granularity, period_name, 1 as sort_order,
            vx_type, region, plant, factory, line,
            anchor_dt as filter_date, snapshot_date as snapshot_date_real,
            total_qty, todo_qty, doing_qty, doing_done_qty, done_qty, acc_qty, acc_total_qty
        FROM gold.rmv_l5_task_summary FINAL
        WHERE period_type = 'Month'
          AND period_key = formatDateTime(anchor_dt, '%Y-%m')
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffRegion.filter('region')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffPlant.filter('plant')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffFactory.filter('factory')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffLine.filter('line')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffVxType.filter('vx_type')}

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
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffRegion.filter('region')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffPlant.filter('plant')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffFactory.filter('factory')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffLine.filter('line')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffVxType.filter('vx_type')}

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
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffRegion.filter('region')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffPlant.filter('plant')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffFactory.filter('factory')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffLine.filter('line')}
          AND ${FILTER_PARAMS.L5TaskPeriodic.diffVxType.filter('vx_type')}
    )
    `,

    measures: {
        // [數量指標]：從預聚合表讀取整數並加總
        totalQty: { type: `sum`, sql: `total_qty`, title: 'QTY: Total' },
        todoQty: { type: `sum`, sql: `todo_qty`, title: 'QTY: Todo' },
        doingQty: { type: `sum`, sql: `doing_qty`, title: 'QTY: Doing' },
        doneQty: { type: `sum`, sql: `done_qty`, title: 'QTY: Done' },

        // [複合指標]
        doingDoneQty: { type: `sum`, sql: `doing_done_qty`, title: 'QTY: Doing+Done' },
        accQty: { type: `sum`, sql: `acc_qty`, title: 'QTY: Todo+Doing(Acc)' },
        accTotalQty: { type: `sum`, sql: `acc_total_qty`, title: 'QTY: Acc Total' },

        effectiveDenominator: { type: `sum`, sql: `total_qty`, title: 'Denominator' },

        // [達成率指標]
        // 規格：數值=1顯示100%；數值<1最大顯示99%；原始比率小數後第3位起無條件捨去後×100顯示整數
        // 公式：if(分子>=分母, 100, floor(分子*100/分母))
        todoRate: {
            type: `number`,
            sql: `floor(${todoQty} * 100.0 / nullIf(${effectiveDenominator}, 0))`,
            title: 'Rate: Todo'
        },
        doingRate: {
            type: `number`,
            sql: `floor(${doingQty} * 100.0 / nullIf(${effectiveDenominator}, 0))`,
            title: 'Rate: Doing'
        },
        doneRate: {
            type: `number`,
            sql: `if(${doneQty} >= ${effectiveDenominator}, 100, floor(${doneQty} * 100.0 / nullIf(${effectiveDenominator}, 0)))`,
            title: 'Rate: Done'
        },
        doingDoneRate: {
            type: `number`,
            sql: `if(${doingDoneQty} >= ${effectiveDenominator}, 100, floor(${doingDoneQty} * 100.0 / nullIf(${effectiveDenominator}, 0)))`,
            title: 'Rate: Doing+Done'
        },
        accRate: {
            type: `number`,
            sql: `
            CASE
                WHEN any(granularity) = 'Day' THEN if(${accQty} >= ${accTotalQty}, 100, floor(${accQty} * 100.0 / nullIf(${accTotalQty}, 0)))
                ELSE floor((${todoQty} + ${doingQty}) * 100.0 / nullIf(${totalQty}, 0))
            END`,
            title: 'Rate: Acc (積壓/落後率)'
        },

        periodSortOrder: { type: `max`, sql: `sort_order`, title: '排序用(Hidden)' }
    },

    dimensions: {
        // [時間維度]
        periodName: { type: `string`, sql: `period_name`, title: '週期/日期名' },
        snapshotDate: { type: `string`, sql: `filter_date`, title: '日期篩選(基準日期)' },
        realSnapshotDate: { type: `string`, sql: `formatDateTime(snapshot_date_real, '%Y-%m-%d')`, title: '實際快照日期' },
        granularity: { type: `string`, sql: `granularity`, title: '粒度' },

        // [製造維度]
        diffVxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' },
        diffRegion: { type: `string`, sql: `region`, title: '地區' },
        diffPlant: { type: `string`, sql: `plant`, title: '廠區' },
        diffFactory: { type: `string`, sql: `factory`, title: '工廠' },
        diffLine: { type: `string`, sql: `line`, title: '線體' }
    }
});
