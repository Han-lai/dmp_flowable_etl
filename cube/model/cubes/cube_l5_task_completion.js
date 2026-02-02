/**
 * L5 任務完成率 Cube - 整合版
 * 
 * 來源表: gold.rmv_l5_task_completion (REFRESHABLE MView，每小時刷新)
 * 用途: 為 Superset L5 任務執行完成度 Dashboard 提供資料模型
 * 
 * 更新記錄 (2026-01-30):
 * - 整合 L5TaskCompletion 和 L5DashboardSummary 為單一 Cube
 * - 使用新的 Gold 層表 gold.rmv_l5_task_completion
 * - 欄位: todo_count, doing_count, done_count, completion_rate, execution_rate
 */

cube(`L5TaskCompletion`, {
    sql: `SELECT * FROM gold.rmv_l5_task_completion FINAL`,

    title: 'L5 任務完成率',
    description: 'L5 任務執行完成度指標，支援 Dashboard 需求',

    measures: {
        // ============================================================
        // 任務狀態數量
        // ============================================================
        totalTask: {
            type: `sum`,
            sql: `total_task`,
            title: '任務總數',
        },

        todoCount: {
            type: `sum`,
            sql: `todo_count`,
            title: 'Todo 數量',
        },

        doingCount: {
            type: `sum`,
            sql: `doing_count`,
            title: 'Doing 數量',
        },

        doneCount: {
            type: `sum`,
            sql: `done_count`,
            title: 'Done 數量',
        },

        // ============================================================
        // 組合指標
        // ============================================================
        doingDoneCount: {
            type: `number`,
            sql: `${doingCount} + ${doneCount}`,
            title: 'Doing + Done 數量',
        },

        todoDoingCount: {
            type: `number`,
            sql: `${todoCount} + ${doingCount}`,
            title: 'Todo + Doing 數量',
        },

        // ============================================================
        // 比例指標
        // ============================================================
        todoRate: {
            type: `number`,
            sql: `CASE WHEN ${totalTask} > 0 THEN ${todoCount} * 100.0 / ${totalTask} ELSE 0 END`,
            title: 'Todo 比例 (%)',
            format: `percent`,
        },

        doingRate: {
            type: `number`,
            sql: `CASE WHEN ${totalTask} > 0 THEN ${doingCount} * 100.0 / ${totalTask} ELSE 0 END`,
            title: 'Doing 比例 (%)',
            format: `percent`,
        },

        doneRate: {
            type: `number`,
            sql: `CASE WHEN ${totalTask} > 0 THEN ${doneCount} * 100.0 / ${totalTask} ELSE 0 END`,
            title: 'Done 比例 (%)',
            format: `percent`,
        },

        completionRate: {
            type: `avg`,
            sql: `completion_rate`,
            title: '完成率 (%)',
            format: `percent`,
        },

        executionRate: {
            type: `avg`,
            sql: `execution_rate`,
            title: '執行率 (%)',
            format: `percent`,
        },
    },

    dimensions: {
        // ============================================================
        // 時間維度
        // ============================================================
        snapshotDate: {
            type: `time`,
            sql: `snapshot_date`,
            title: '快照日期',
        },

        // ============================================================
        // 製造五階維度
        // ============================================================
        vxType: {
            type: `string`,
            sql: `vx_type`,
            title: 'Vx 類型',
        },

        region: {
            type: `string`,
            sql: `COALESCE(NULLIF(region, ''), 'UNKNOWN')`,
            title: '地區',
        },

        plant: {
            type: `string`,
            sql: `COALESCE(NULLIF(plant, ''), 'UNKNOWN')`,
            title: '廠區',
        },

        factory: {
            type: `string`,
            sql: `COALESCE(NULLIF(factory, ''), 'UNKNOWN')`,
            title: '工廠',
        },

        line: {
            type: `string`,
            sql: `COALESCE(NULLIF(line, ''), '')`,
            title: '線體',
        },

        // ============================================================
        // 組合維度
        // ============================================================
        locationPath: {
            type: `string`,
            sql: `CONCAT(
        COALESCE(NULLIF(region, ''), 'UNKNOWN'), '-',
        COALESCE(NULLIF(plant, ''), 'UNKNOWN'), '-',
        COALESCE(NULLIF(factory, ''), 'UNKNOWN')
      )`,
            title: '位置路徑',
        },

        // ============================================================
        // Metadata
        // ============================================================
        refreshTime: {
            type: `time`,
            sql: `_refresh_time`,
            title: '刷新時間',
        },
    },

    preAggregations: {
        // 按日期 + Vx 類型 + 廠區聚合
        dailyVxSummary: {
            measures: [
                L5TaskCompletion.totalTask,
                L5TaskCompletion.todoCount,
                L5TaskCompletion.doingCount,
                L5TaskCompletion.doneCount,
            ],
            dimensions: [
                L5TaskCompletion.snapshotDate,
                L5TaskCompletion.vxType,
                L5TaskCompletion.region,
                L5TaskCompletion.plant,
            ],
            timeDimension: L5TaskCompletion.snapshotDate,
            granularity: `day`,
            refreshKey: {
                every: `1 hour`,
            },
        },

        // 完整維度聚合
        fullDimensionSummary: {
            measures: [
                L5TaskCompletion.totalTask,
                L5TaskCompletion.doneCount,
                L5TaskCompletion.completionRate,
            ],
            dimensions: [
                L5TaskCompletion.snapshotDate,
                L5TaskCompletion.region,
                L5TaskCompletion.plant,
                L5TaskCompletion.factory,
                L5TaskCompletion.line,
                L5TaskCompletion.vxType,
            ],
            timeDimension: L5TaskCompletion.snapshotDate,
            granularity: `day`,
            refreshKey: {
                every: `1 hour`,
            },
        },
    },
});
