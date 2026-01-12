/**
 * Gold Layer: Daily Metrics Snapshot
 * 每日指標快照 - 支援歷史趨勢查詢
 * 
 * 來源表: gold.DAILY_METRICS_SNAPSHOT
 * Grain: snapshot_date + factory + plant + proc_def_name
 * 
 * 用途:
 * - 查詢歷史趨勢 (本週 vs 上週、月度趨勢)
 * - 指標回溯 (查詢過去某天的指標值)
 * - 維度聚合 (依 factory/plant/proc_def_name 聚合)
 */

cube(`DailyMetricsSnapshot`, {
  sql: `SELECT * FROM gold.DAILY_METRICS_SNAPSHOT FINAL`,
  
  title: '每日指標快照',
  description: 'Gold 層每日快照，支援歷史趨勢查詢。包含任務層和流程層指標。',

  measures: {
    // ============================================================
    // 🥇 Gold 指標 - 在途任務
    // ============================================================
    inProgressTaskCount: {
      type: `sum`,
      sql: `in_progress_task_count`,
      title: '在途任務數',
      description: '🥇 Gold 指標 - 狀態為 TODO 或 DOING 的任務數量。可跨維度 SUM。',
    },
    
    todoCount: {
      type: `sum`,
      sql: `todo_count`,
      title: '待辦任務數',
      description: '狀態為 TODO 的任務數量',
    },
    
    doingCount: {
      type: `sum`,
      sql: `doing_count`,
      title: '進行中任務數',
      description: '狀態為 DOING 的任務數量',
    },

    // ============================================================
    // 🥇 Gold 指標 - 自動完成率 (分子分母)
    // ============================================================
    doneAutoCount: {
      type: `sum`,
      sql: `done_auto_count`,
      title: '自動完成數',
      description: '自動完成率分子。跨維度聚合時，用 doneAutoCount / doneTotalCount 重算。',
    },
    
    doneTotalCount: {
      type: `sum`,
      sql: `done_total_count`,
      title: '已完成總數',
      description: '自動完成率分母 (DONE + DONE_AUTO)',
    },
    
    autoCompleteRate: {
      type: `number`,
      sql: `CASE WHEN ${doneTotalCount} > 0 THEN ${doneAutoCount} * 100.0 / ${doneTotalCount} ELSE 0 END`,
      title: '自動完成率 (%)',
      description: '🥇 Gold 指標 - DONE_AUTO / (DONE + DONE_AUTO) × 100%。⚠️ 跨維度聚合時需用分子分母重算。',
      format: `percent`,
    },

    // ============================================================
    // 🥇 Gold 指標 - 平均處理時長 (分子分母)
    // ============================================================
    totalWorkDurationSec: {
      type: `sum`,
      sql: `total_work_duration_sec`,
      title: '處理時長總和 (秒)',
      description: '平均處理時長分子',
    },
    
    doneCount: {
      type: `sum`,
      sql: `done_count`,
      title: '已完成任務數',
      description: '平均處理時長分母 (DONE 狀態)',
    },
    
    avgWorkDurationSec: {
      type: `number`,
      sql: `CASE WHEN ${doneCount} > 0 THEN ${totalWorkDurationSec} / ${doneCount} ELSE 0 END`,
      title: '平均處理時長 (秒)',
      description: '🥇 Gold 指標 - 已完成任務的平均處理時長。⚠️ 跨維度聚合時需用分子分母重算。',
    },
    
    avgWorkDurationMin: {
      type: `number`,
      sql: `CASE WHEN ${doneCount} > 0 THEN ${totalWorkDurationSec} / ${doneCount} / 60 ELSE 0 END`,
      title: '平均處理時長 (分鐘)',
      description: '已完成任務的平均處理時長 (分鐘)',
    },

    // ============================================================
    // 🥇 Gold 指標 - 流程實例
    // ============================================================
    inProgressProcCount: {
      type: `sum`,
      sql: `in_progress_proc_count`,
      title: '在途流程數',
      description: '🥇 Gold 指標 - 尚未完成的流程實例數量',
    },
    
    completedProcCount: {
      type: `sum`,
      sql: `completed_proc_count`,
      title: '已完成流程數',
      description: '🥇 Gold 指標 - 已完成的流程實例數量',
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
      description: '快照日期 (Asia/Taipei)',
    },
    
    snapshotTime: {
      type: `time`,
      sql: `snapshot_time`,
      title: '快照時間',
      description: '快照時間戳',
    },

    // ============================================================
    // 業務維度
    // ============================================================
    factory: {
      type: `string`,
      sql: `factory`,
      title: '工廠',
    },
    
    plant: {
      type: `string`,
      sql: `plant`,
      title: '產品線',
    },
    
    procDefName: {
      type: `string`,
      sql: `proc_def_name`,
      title: '流程類型',
    },
  },
});
