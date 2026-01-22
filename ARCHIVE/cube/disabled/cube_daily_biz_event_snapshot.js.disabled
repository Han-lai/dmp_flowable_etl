/**
 * Gold Layer: Daily Business Event Snapshot
 * 每日業務事件快照 - 支援歷史趨勢查詢
 * 
 * 來源表: gold.DAILY_BIZ_EVENT_SNAPSHOT
 * Grain: snapshot_date + first_proc_def_name
 * 
 * 用途:
 * - 查詢業務事件歷史趨勢
 * - 指標回溯 (查詢過去某天的業務事件指標)
 * 
 * 注意:
 * - 此表沒有 factory/plant 維度
 * - 如需按廠區分析，請用 DailyMetricsSnapshot
 */

cube(`DailyBizEventSnapshot`, {
  sql: `SELECT * FROM gold.DAILY_BIZ_EVENT_SNAPSHOT FINAL`,
  
  title: '每日業務事件快照',
  description: 'Gold 層每日業務事件快照。⚠️ 此 Cube 沒有廠區維度。',

  measures: {
    // ============================================================
    // 🥇 Gold 指標 - 業務事件
    // ============================================================
    inProgressEventCount: {
      type: `sum`,
      sql: `in_progress_event_count`,
      title: '在途業務事件數',
      description: '🥇 Gold 指標 - 尚未完成的業務事件數量',
    },
    
    completedEventCount: {
      type: `sum`,
      sql: `completed_event_count`,
      title: '已完成業務事件數',
      description: '已完成的業務事件數量',
    },
    
    totalEventDurationSec: {
      type: `sum`,
      sql: `total_event_duration_sec`,
      title: '業務事件總歷時 (秒)',
      description: '平均業務事件歷時分子',
    },
    
    avgEventDurationSec: {
      type: `number`,
      sql: `CASE WHEN ${completedEventCount} > 0 THEN ${totalEventDurationSec} / ${completedEventCount} ELSE 0 END`,
      title: '平均業務事件歷時 (秒)',
      description: '🥇 Gold 指標 - 已完成業務事件的平均總歷時。⚠️ 跨維度聚合時需用分子分母重算。',
    },
    
    avgEventDurationHour: {
      type: `number`,
      sql: `CASE WHEN ${completedEventCount} > 0 THEN ${totalEventDurationSec} / ${completedEventCount} / 3600 ELSE 0 END`,
      title: '平均業務事件歷時 (小時)',
      description: '已完成業務事件的平均總歷時 (小時)',
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
    firstProcDefName: {
      type: `string`,
      sql: `first_proc_def_name`,
      title: '首個流程類型',
      description: '業務事件的首個流程定義名稱',
    },
  },
});
