/**
 * L5 任務執行完成度 Cube - 使用新的 REFRESHABLE MView
 * 
 * 來源表: gold.rmv_l5_task_completion (新的 REFRESHABLE MView)
 * 用途: 為 L5 任務執行完成度 Dashboard 提供完整的資料模型
 * 
 * 更新記錄 (2026-01-30):
 * - 更新為新的 Gold 層表 gold.rmv_l5_task_completion
 * - 表格每小時自動刷新 (REFRESH EVERY 1 HOUR)
 * - 欄位名稱更新: todo_task → todo_count, doing_task → doing_count, done_task → done_count
 */

cube(`L5TaskCompletion`, {
  sql: `SELECT * FROM gold.rmv_l5_task_completion FINAL`,

  title: 'L5 任務完成率',
  description: '基於 REFRESHABLE MView 的 L5 任務完成率指標',

  measures: {
    // ============================================================
    // 任務狀態數量
    // ============================================================
    totalTask: {
      type: `sum`,
      sql: `total_task`,
      title: '任務總數',
      description: '該時間區間內任務總數',
    },

    todoCount: {
      type: `sum`,
      sql: `todo_count`,
      title: 'Todo 數量',
      description: '尚未開始之任務',
    },

    doingCount: {
      type: `sum`,
      sql: `doing_count`,
      title: 'Doing 數量',
      description: '執行中之任務',
    },

    doneCount: {
      type: `sum`,
      sql: `done_count`,
      title: 'Done 數量',
      description: '已完成之任務',
    },

    // ============================================================
    // 組合指標
    // ============================================================
    doingDoneCount: {
      type: `number`,
      sql: `${doingCount} + ${doneCount}`,
      title: 'Doing + Done 數量',
      description: '已處理任務總數',
    },

    // ============================================================
    // 比例指標
    // ============================================================
    completionRate: {
      type: `avg`,
      sql: `completion_rate`,
      title: '完成率 (%)',
      description: 'done_count / total_task × 100%',
      format: `percent`,
    },

    executionRate: {
      type: `avg`,
      sql: `execution_rate`,
      title: '執行率 (%)',
      description: '(doing_count + done_count) / total_task × 100%',
      format: `percent`,
    },

    // 動態計算的完成率
    calculatedCompletionRate: {
      type: `number`,
      sql: `CASE WHEN ${totalTask} > 0 THEN ${doneCount} * 100.0 / ${totalTask} ELSE 0 END`,
      title: '計算完成率 (%)',
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
      description: '任務日期',
    },

    // ============================================================
    // 製造五階維度
    // ============================================================
    vxType: {
      type: `string`,
      sql: `vx_type`,
      title: 'Vx 類型',
      description: 'V1 / V2 / V3',
    },

    region: {
      type: `string`,
      sql: `COALESCE(NULLIF(region, ''), 'UNKNOWN')`,
      title: '地區',
      description: '地區（如：CNE）',
    },

    plant: {
      type: `string`,
      sql: `COALESCE(NULLIF(plant, ''), 'UNKNOWN')`,
      title: '廠區',
      description: '廠區（如：WJ2）',
    },

    factory: {
      type: `string`,
      sql: `COALESCE(NULLIF(factory, ''), 'UNKNOWN')`,
      title: '工廠',
      description: '工廠（如：NBU）',
    },

    line: {
      type: `string`,
      sql: `COALESCE(NULLIF(line, ''), '')`,
      title: '線體',
      description: '線體（如：E5）',
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
      description: 'Region-Plant-Factory',
    },

    // ============================================================
    // Metadata
    // ============================================================
    refreshTime: {
      type: `time`,
      sql: `_refresh_time`,
      title: '刷新時間',
      description: 'MView 刷新時間',
    },
  },

  preAggregations: {
    // 按日期 + Vx 類型聚合
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
  },
});