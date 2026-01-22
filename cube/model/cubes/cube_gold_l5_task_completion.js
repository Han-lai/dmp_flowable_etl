/**
 * Gold Layer: L5 Task Completion Snapshot (基於新 MView 架構)
 * L5 任務完成率快照 - 基於 gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
 * 
 * 來源表: gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
 * Grain: snapshot_date + plant + factory + line + vx_type + vx_subtype
 * 
 * 用途:
 * - L5 指標歷史趨勢查詢
 * - 任務完成率回溯分析
 * - Vx 類型維度聚合
 * - NPE vs MFG 對比分析
 */

cube(`GoldL5TaskCompletion`, {
  sql: `SELECT * FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL`,
  
  title: 'L5 任務完成率快照 (Gold)',
  description: 'Gold 層 L5 任務完成率指標快照，支援 NPE/MFG 子類型分析和歷史趨勢查詢。',

  measures: {
    // ============================================================
    // 🥇 L5 核心任務數量指標
    // ============================================================
    totalTasks: {
      type: `sum`,
      sql: `sum_total_task_qty`,
      title: 'L5 總任務數',
      description: '🥇 L5 核心指標 - 未被排除的總任務數量',
    },
    
    todoTasks: {
      type: `sum`,
      sql: `sum_todo_qty`,
      title: 'L5 待辦任務數',
      description: 'L5 指標 - 狀態為 TODO 的任務數量',
    },
    
    doingTasks: {
      type: `sum`,
      sql: `sum_doing_qty`,
      title: 'L5 進行中任務數',
      description: 'L5 指標 - 狀態為 DOING 的任務數量',
    },

    doneTasks: {
      type: `sum`,
      sql: `sum_done_qty`,
      title: 'L5 已完成任務數',
      description: 'L5 指標 - 狀態為 DONE 的任務數量',
    },

    excludedTasks: {
      type: `sum`,
      sql: `sum_excluded_qty`,
      title: 'L5 排除任務數',
      description: 'L5 指標 - 被排除的任務數量 (bypass/E/C/Q/R)',
    },

    inProgressTasks: {
      type: `number`,
      sql: `${doingTasks} + ${doneTasks}`,
      title: 'L5 在途任務數',
      description: '🥇 L5 指標 - 進行中 + 已完成任務數 (DOING + DONE)',
    },

    // ============================================================
    // 🥇 L5 完成率指標 (百分比)
    // ============================================================
    completionRate: {
      type: `number`,
      sql: `CASE WHEN ${totalTasks} > 0 THEN ${doneTasks} * 100.0 / ${totalTasks} ELSE 0 END`,
      title: 'L5 任務完成率 (%)',
      description: '🥇 L5 核心指標 - DONE / 總任務數 × 100%',
      format: `percent`,
    },

    progressRate: {
      type: `number`,
      sql: `CASE WHEN ${totalTasks} > 0 THEN ${inProgressTasks} * 100.0 / ${totalTasks} ELSE 0 END`,
      title: 'L5 任務執行率 (%)',
      description: '🥇 L5 核心指標 - (DOING + DONE) / 總任務數 × 100%',
      format: `percent`,
    },

    // ============================================================
    // 📊 排除原因統計
    // ============================================================
    bypassTasks: {
      type: `sum`,
      sql: `sum_bypass_qty`,
      title: '旁路任務數',
      description: 'TaskBypass != N 的任務數量',
    },

    ePrefixTasks: {
      type: `sum`,
      sql: `sum_e_prefix_qty`,
      title: 'E 前綴任務數',
      description: 'TaskDefinitionKey 以 E 開頭的任務數量',
    },

    cPrefixTasks: {
      type: `sum`,
      sql: `sum_c_prefix_qty`,
      title: 'C 前綴任務數',
      description: 'TaskDefinitionKey 以 C 開頭的任務數量',
    },

    qOrderTasks: {
      type: `sum`,
      sql: `sum_q_order_qty`,
      title: 'Q 工單任務數',
      description: '工單號以 Q 開頭的任務數量',
    },

    rOrderTasks: {
      type: `sum`,
      sql: `sum_r_order_qty`,
      title: 'R 工單任務數',
      description: '工單號以 R 開頭的任務數量',
    },

    specialV1RuleTasks: {
      type: `sum`,
      sql: `sum_special_v1_rule_qty`,
      title: '特殊 V1 規則任務數',
      description: '套用工單號規則的 V1 任務數量 (196/199/200/210/212/213/315)',
    },

    // ============================================================
    // 📊 預計算完成率 (來自 MView)
    // ============================================================
    preCalculatedCompletionRate: {
      type: `avg`,
      sql: `completion_rate`,
      title: '預計算完成率 (%)',
      description: 'MView 中預計算的完成率 (單一維度組合用)',
      format: `percent`,
    },

    preCalculatedProgressRate: {
      type: `avg`,
      sql: `progress_rate`,
      title: '預計算執行率 (%)',
      description: 'MView 中預計算的執行率 (單一維度組合用)',
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
      description: 'L5 指標快照日期',
    },

    // ============================================================
    // L5 業務維度
    // ============================================================
    vxType: {
      type: `string`,
      sql: `vx_type`,
      title: 'Vx 類型',
      description: 'V1 / V2 / V3',
    },

    vxSubtype: {
      type: `string`,
      sql: `vx_subtype`,
      title: 'Vx 子類型',
      description: 'V1_NPE / V1_MFG (僅 V1 有子類型)',
    },

    // ============================================================
    // 廠區維度
    // ============================================================
    plant: {
      type: `string`,
      sql: `plant`,
      title: '廠區',
      description: '廠區代碼',
    },
    
    factory: {
      type: `string`,
      sql: `factory`,
      title: '工廠',
      description: '工廠代碼',
    },

    line: {
      type: `string`,
      sql: `line`,
      title: '產線',
      description: '產線代碼',
    },

    // ============================================================
    // 組合維度 (用於分組)
    // ============================================================
    plantFactory: {
      type: `string`,
      sql: `CONCAT(plant, '|', factory)`,
      title: '廠區-工廠',
      description: '廠區和工廠的組合維度',
    },

    factoryLine: {
      type: `string`,
      sql: `CONCAT(factory, '|', line)`,
      title: '工廠-產線',
      description: '工廠和產線的組合維度',
    },

    vxTypeSubtype: {
      type: `string`,
      sql: `CONCAT(vx_type, CASE WHEN vx_subtype != '' THEN CONCAT('_', vx_subtype) ELSE '' END)`,
      title: 'Vx 完整類型',
      description: 'Vx 類型和子類型的組合 (如 V1_NPE, V1_MFG, V2, V3)',
    },

    // ============================================================
    // Metadata
    // ============================================================
    lastUpdated: {
      type: `time`,
      sql: `_mview_update_time`,
      title: '最後更新時間',
      description: 'MView 最後更新時間',
    },
  },

  // ============================================================
  // 預聚合配置 (提升查詢效能)
  // ============================================================
  preAggregations: {
    // 按日期 + Vx 類型聚合
    dailyVxSummary: {
      measures: [
        GoldL5TaskCompletion.totalTasks,
        GoldL5TaskCompletion.doneTasks,
        GoldL5TaskCompletion.doingTasks,
        GoldL5TaskCompletion.todoTasks,
        GoldL5TaskCompletion.excludedTasks,
      ],
      dimensions: [
        GoldL5TaskCompletion.snapshotDate,
        GoldL5TaskCompletion.vxType,
        GoldL5TaskCompletion.vxSubtype,
      ],
      timeDimension: GoldL5TaskCompletion.snapshotDate,
      granularity: `day`,
      refreshKey: {
        every: `1 hour`,
      },
    },

    // 按廠區聚合
    factorySummary: {
      measures: [
        GoldL5TaskCompletion.totalTasks,
        GoldL5TaskCompletion.doneTasks,
        GoldL5TaskCompletion.inProgressTasks,
      ],
      dimensions: [
        GoldL5TaskCompletion.snapshotDate,
        GoldL5TaskCompletion.plant,
        GoldL5TaskCompletion.factory,
        GoldL5TaskCompletion.vxType,
      ],
      timeDimension: GoldL5TaskCompletion.snapshotDate,
      granularity: `day`,
      refreshKey: {
        every: `1 hour`,
      },
    },
  },
});