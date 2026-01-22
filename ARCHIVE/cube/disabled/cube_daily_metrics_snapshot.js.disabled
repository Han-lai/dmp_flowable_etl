/**
 * Gold Layer: Daily L5 Task Completion Snapshot
 * L5 任務完成率每日快照 - 支援歷史趨勢查詢
 * 
 * 來源表: gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
 * Grain: snapshot_date + vx_type + plant + factory + line + time_period
 * 
 * 用途:
 * - L5 指標歷史趨勢查詢
 * - 任務完成率回溯分析
 * - Vx 類型維度聚合
 */

cube(`DailyMetricsSnapshot`, {
  sql: `SELECT * FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL`,
  
  title: 'L5 每日指標快照',
  description: 'L5 任務完成率指標的每日快照，支援歷史趨勢查詢和 Vx 類型分析。',

  measures: {
    // ============================================================
    // 🥇 L5 核心指標
    // ============================================================
    l5TotalTaskQty: {
      type: `sum`,
      sql: `total_task_qty`,
      title: 'L5 總任務數',
      description: '🥇 L5 指標 - 未被排除的總任務數量',
    },
    
    l5TodoQty: {
      type: `sum`,
      sql: `todo_qty`,
      title: 'L5 待辦任務數',
      description: 'L5 指標 - 狀態為 TODO 的任務數量',
    },
    
    l5DoingQty: {
      type: `sum`,
      sql: `doing_qty`,
      title: 'L5 進行中任務數',
      description: 'L5 指標 - 狀態為 DOING 的任務數量',
    },

    l5DoneQty: {
      type: `sum`,
      sql: `done_qty`,
      title: 'L5 已完成任務數',
      description: 'L5 指標 - 狀態為 DONE 的任務數量',
    },

    l5InProgressQty: {
      type: `sum`,
      sql: `doing_done_qty`,
      title: 'L5 在途任務數',
      description: '🥇 L5 指標 - 進行中 + 已完成任務數 (DOING + DONE)',
    },

    l5TodoDoingAccQty: {
      type: `sum`,
      sql: `todo_doing_acc_qty`,
      title: 'L5 累計在途任務數',
      description: 'L5 指標 - 待辦 + 進行中累計數 (TODO + DOING Acc)',
    },

    // ============================================================
    // 🥇 L5 完成率指標 (百分比)
    // ============================================================
    l5TodoPct: {
      type: `avg`,
      sql: `todo_pct`,
      title: 'L5 待辦率 (%)',
      description: 'L5 指標 - TODO / 總任務數 × 100%',
      format: `percent`,
    },

    l5DoingPct: {
      type: `avg`,
      sql: `doing_pct`,
      title: 'L5 進行中率 (%)',
      description: 'L5 指標 - DOING / 總任務數 × 100%',
      format: `percent`,
    },

    l5DonePct: {
      type: `avg`,
      sql: `done_pct`,
      title: 'L5 完成率 (%)',
      description: '🥇 L5 核心指標 - DONE / 總任務數 × 100%',
      format: `percent`,
    },

    l5DoingDonePct: {
      type: `avg`,
      sql: `doing_done_pct`,
      title: 'L5 執行率 (%)',
      description: '🥇 L5 核心指標 - (DOING + DONE) / 總任務數 × 100%',
      format: `percent`,
    },

    // ============================================================
    // 📊 計算用分子分母 (跨維度聚合用)
    // ============================================================
    l5CompletionRate: {
      type: `number`,
      sql: `CASE WHEN ${l5TotalTaskQty} > 0 THEN ${l5DoneQty} * 100.0 / ${l5TotalTaskQty} ELSE 0 END`,
      title: 'L5 任務完成率 (%)',
      description: '🥇 L5 核心指標 - 跨維度聚合用完成率計算',
      format: `percent`,
    },

    l5ExecutionRate: {
      type: `number`,
      sql: `CASE WHEN ${l5TotalTaskQty} > 0 THEN ${l5InProgressQty} * 100.0 / ${l5TotalTaskQty} ELSE 0 END`,
      title: 'L5 任務執行率 (%)',
      description: '🥇 L5 核心指標 - 跨維度聚合用執行率計算',
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
      description: 'V1_NPE / V1_MFG',
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
      title: '產線',
    },

    timePeriodType: {
      type: `string`,
      sql: `time_period_type`,
      title: '時間區間類型',
      description: 'daily / weekly / monthly',
    },

    timePeriodValue: {
      type: `string`,
      sql: `time_period_value`,
      title: '時間區間值',
      description: '具體的時間區間值',
    },
  },
});
