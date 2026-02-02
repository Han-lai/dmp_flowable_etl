/**
 * L5 Dashboard Summary Cube - 儀表板專用彙總模型
 * 
 * 來源表: gold.rmv_l5_task_completion (新的 REFRESHABLE MView)
 * 用途: 為 Superset 儀表板提供標準化的 L5 任務指標
 * 
 * 更新記錄 (2026-01-30):
 * - 更新為新的 Gold 層表 gold.rmv_l5_task_completion
 * - 欄位名稱更新: todo_task → todo_count, doing_task → doing_count, done_task → done_count
 * - 移除不存在的欄位（維度來源追蹤等）
 */

cube(`L5DashboardSummary`, {
  sql: `SELECT * FROM gold.rmv_l5_task_completion FINAL`,

  title: 'L5 任務儀表板彙總',
  description: '為 Superset 儀表板提供的標準化 L5 任務指標彙總表',

  measures: {
    // ============================================================
    // 任務狀態彙總欄位
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
    // 計算指標
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
    // 比例欄位
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
    // 主鍵維度
    // ============================================================
    snapshotDate: {
      type: `time`,
      sql: `snapshot_date`,
      title: '快照日期',
    },

    region: {
      type: `string`,
      sql: `region`,
      title: '地區',
    },

    plant: {
      type: `string`,
      sql: `plant`,
      title: '廠區',
    },

    factory: {
      type: `string`,
      sql: `factory`,
      title: '工廠',
    },

    line: {
      type: `string`,
      sql: `line`,
      title: '線體',
    },

    vxType: {
      type: `string`,
      sql: `vx_type`,
      title: 'Vx 類型',
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
    // 按日期 + Vx 類型聚合
    dailyVxSummary: {
      measures: [
        L5DashboardSummary.totalTask,
        L5DashboardSummary.todoCount,
        L5DashboardSummary.doingCount,
        L5DashboardSummary.doneCount,
      ],
      dimensions: [
        L5DashboardSummary.snapshotDate,
        L5DashboardSummary.vxType,
        L5DashboardSummary.region,
        L5DashboardSummary.plant,
      ],
      timeDimension: L5DashboardSummary.snapshotDate,
      granularity: `day`,
      refreshKey: {
        every: `1 hour`,
      },
    },

    // 完整維度聚合
    fullDimensionSummary: {
      measures: [
        L5DashboardSummary.totalTask,
        L5DashboardSummary.doneCount,
        L5DashboardSummary.completionRate,
      ],
      dimensions: [
        L5DashboardSummary.snapshotDate,
        L5DashboardSummary.region,
        L5DashboardSummary.plant,
        L5DashboardSummary.factory,
        L5DashboardSummary.line,
        L5DashboardSummary.vxType,
      ],
      timeDimension: L5DashboardSummary.snapshotDate,
      granularity: `day`,
      refreshKey: {
        every: `1 hour`,
      },
    },
  },
});