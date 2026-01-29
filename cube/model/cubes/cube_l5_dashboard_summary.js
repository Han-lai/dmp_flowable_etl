/**
 * L5 Dashboard Summary Cube - 儀表板專用彙總模型
 * 
 * 來源表: gold.l5_dashboard_summary
 * 用途: 為 Superset 儀表板提供標準化的 L5 任務指標
 * 
 * Schema 對應:
 * - 主鍵維度: snapshot_date, region, plant, factory, line, vx_type
 * - 任務狀態: total_task, todo_task, doing_task, done_task
 * - 維度來源追蹤: region_source, plant_source, factory_source, line_source
 * - 使用 Silver 層補齊後的完整五階維度，包含 VARINST 優先、MDM 補齊邏輯
 */

cube(`L5DashboardSummary`, {
  sql: `SELECT * FROM gold.l5_dashboard_summary`,

  title: 'L5 任務儀表板彙總',
  description: '為 Superset 儀表板提供的標準化 L5 任務指標彙總表',

  measures: {
    // ============================================================
    // 任務狀態彙總欄位 - 使用實際表格欄位名稱
    // ============================================================
    totalTask: {
      type: `sum`,
      sql: `total_task`,
      title: '任務總數',
      description: '任務總數 (total_task)',
    },

    todoTask: {
      type: `sum`,
      sql: `todo_task`,
      title: 'Todo 數量',
      description: 'Todo 狀態任務數量',
    },

    doingTask: {
      type: `sum`,
      sql: `doing_task`,
      title: 'Doing 數量',
      description: 'Doing 狀態任務數量',
    },

    doneTask: {
      type: `sum`,
      sql: `done_task`,
      title: 'Done 數量',
      description: 'Done 狀態任務數量',
    },

    // ============================================================
    // 計算指標 - 基於實際欄位計算
    // ============================================================
    doingDoneTask: {
      type: `number`,
      sql: `${doingTask} + ${doneTask}`,
      title: 'Doing + Done 數量',
      description: 'Doing + Done 任務數量',
    },

    todoDoingTask: {
      type: `number`,
      sql: `${todoTask} + ${doingTask}`,
      title: 'Todo + Doing 數量',
      description: 'Todo + Doing 任務數量（累計在途）',
    },

    // ============================================================
    // 比例欄位（計算指標）
    // ============================================================
    todoRate: {
      type: `number`,
      sql: `CASE WHEN ${totalTask} > 0 THEN ${todoTask} * 100.0 / ${totalTask} ELSE 0 END`,
      title: 'Todo 比例 (%)',
      description: 'todo_task / total_task * 100%',
      format: `percent`,
    },

    doingRate: {
      type: `number`,
      sql: `CASE WHEN ${totalTask} > 0 THEN ${doingTask} * 100.0 / ${totalTask} ELSE 0 END`,
      title: 'Doing 比例 (%)',
      description: 'doing_task / total_task * 100%',
      format: `percent`,
    },

    doneRate: {
      type: `number`,
      sql: `CASE WHEN ${totalTask} > 0 THEN ${doneTask} * 100.0 / ${totalTask} ELSE 0 END`,
      title: 'Done 比例 (%)',
      description: 'done_task / total_task * 100%',
      format: `percent`,
    },

    completionRate: {
      type: `avg`,
      sql: `completion_rate`,
      title: '完成率 (%)',
      description: '預計算的完成率',
      format: `percent`,
    },


  },

  dimensions: {
    // ============================================================
    // 主鍵維度欄位 - 使用補齊後的維度
    // ============================================================
    snapshotDate: {
      type: `time`,
      sql: `snapshot_date`,
      title: '快照日期',
      description: '快照日期（每日）',
    },

    region: {
      type: `string`,
      sql: `region`,
      title: '地區',
      description: '地區（製造五階）- 使用 VARINST 優先、MDM 補齊邏輯',
    },

    plant: {
      type: `string`,
      sql: `plant`,
      title: '廠別',
      description: '廠別代碼 - 使用 VARINST 優先、MDM 補齊邏輯',
    },

    factory: {
      type: `string`,
      sql: `factory`,
      title: '工廠',
      description: '工廠代碼 - 使用 VARINST 優先、MDM 補齊邏輯',
    },

    line: {
      type: `string`,
      sql: `line`,
      title: '線體',
      description: '線體代碼 - 使用 VARINST 優先、MDM 補齊邏輯',
    },

    vxType: {
      type: `string`,
      sql: `vx_type`,
      title: 'Vx 類型',
      description: 'V1 / V2 / V3',
    },



    // ============================================================
    // Metadata
    // ============================================================
    lastUpdated: {
      type: `time`,
      sql: `_update_time`,
      title: '最後更新時間',
      description: '資料最後更新時間',
    },
  },

  // ============================================================
  // 預聚合配置（提升 Superset 查詢效能）
  // ============================================================
  preAggregations: {
    // 按日期 + Vx 類型聚合
    dailyVxSummary: {
      measures: [
        L5DashboardSummary.totalTask,
        L5DashboardSummary.todoTask,
        L5DashboardSummary.doingTask,
        L5DashboardSummary.doneTask,
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

    // 按完整維度聚合
    fullDimensionSummary: {
      measures: [
        L5DashboardSummary.totalTask,
        L5DashboardSummary.doneTask,
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