/**
 * Gold Layer: User Utilization Rate (人員使用率) - 更新版本
 * 基於指標定義文件的人員使用率 Cube
 * 
 * 來源表: gold.DAILY_USER_UTILIZATION_SNAPSHOT (Gold 層快照表)
 * 輔助表: silver.mv_dim_config_user (Config Users), silver.mv_fact_task_vx_attribution (Active Users)
 * Grain: snapshot_date + vx_type + plant + factory + line + time_period
 * 
 * 更新記錄 (2026-01-23):
 * - 已替換為原生 Flowable 表邏輯
 * - 使用實際的 Gold 層快照表
 * - 支援時間區間分析 (Total/Month/Week/Daily)
 * 
 * 用途:
 * - 人員使用率計算 (Active Users / Config Users)
 * - 支援 Vx/Plant/Factory/Line 維度篩選
 * - 支援時間區間分析
 */

cube(`GoldUserUtilization`, {
  sql: `SELECT * FROM gold.DAILY_USER_UTILIZATION_SNAPSHOT FINAL`,
  
  title: '人員使用率 (Gold)',
  description: '基於指標定義文件的人員使用率指標，支援 Active Users / Config Users 計算。',

  measures: {
    // ============================================================
    // 🥇 人員使用率核心指標 (基於 Gold 層快照表)
    // ============================================================
    configUsers: {
      type: `sum`,
      sql: `config_users`,
      title: 'Config Users',
      description: '🥇 具備對應系統使用權限的人員數',
    },
    
    activeUsers: {
      type: `sum`,
      sql: `active_users`,
      title: 'Active Users',
      description: '🥇 實際有使用紀錄的人員數',
    },

    utilizationRate: {
      type: `avg`,
      sql: `utilization_rate`,
      title: '人員使用率 (%)',
      description: '🥇 Active Users / Config Users × 100% (預計算)',
      format: `percent`,
    },

    // ============================================================
    // 📊 計算指標 (即時計算)
    // ============================================================
    calculatedUtilizationRate: {
      type: `number`,
      sql: `CASE WHEN ${configUsers} > 0 THEN ${activeUsers} * 100.0 / ${configUsers} ELSE 0 END`,
      title: '計算使用率 (%)',
      description: '即時計算的 Active Users / Config Users × 100%',
      format: `percent`,
    },

    // ============================================================
    // 📊 輔助統計指標
    // ============================================================
    avgConfigUsers: {
      type: `avg`,
      sql: `config_users`,
      title: '平均 Config Users',
      description: '平均具備權限的人員數',
    },

    avgActiveUsers: {
      type: `avg`,
      sql: `active_users`,
      title: '平均 Active Users',
      description: '平均活躍人員數',
    },

    maxConfigUsers: {
      type: `max`,
      sql: `config_users`,
      title: '最大 Config Users',
      description: '最大具備權限的人員數',
    },

    maxActiveUsers: {
      type: `max`,
      sql: `active_users`,
      title: '最大 Active Users',
      description: '最大活躍人員數',
    },

    totalRecords: {
      type: `count`,
      title: '記錄總數',
      description: '快照記錄總數',
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
      description: '人員使用率快照日期',
    },

    // ============================================================
    // 時間區間維度 (基於 Gold 層快照表)
    // ============================================================
    timePeriodType: {
      type: `string`,
      sql: `time_period_type`,
      title: '時間區間類型',
      description: 'Total/Month/Week/Daily',
    },

    timePeriodValue: {
      type: `string`,
      sql: `time_period_value`,
      title: '時間區間值',
      description: '具體的時間區間值',
    },

    // ============================================================
    // 業務維度 (依指標定義文件)
    // ============================================================
    vxType: {
      type: `string`,
      sql: `vx_type`,
      title: 'Vx',
      description: 'V1 / V2 / V3',
    },

    plant: {
      type: `string`,
      sql: `plant`,
      title: 'Plant',
      description: '產品線',
    },
    
    factory: {
      type: `string`,
      sql: `factory`,
      title: 'Factory',
      description: '工廠代碼',
    },

    line: {
      type: `string`,
      sql: `line`,
      title: 'Line',
      description: '產線代碼',
    },

    // ============================================================
    // 組合維度
    // ============================================================
    vxPlant: {
      type: `string`,
      sql: `CONCAT(vx_type, '-', plant)`,
      title: 'Vx-Plant',
      description: 'Vx 類型和產品線的組合',
    },

    vxPlantFactory: {
      type: `string`,
      sql: `CONCAT(vx_type, '-', plant, '-', factory)`,
      title: 'Vx-Plant-Factory',
      description: 'Vx 類型、產品線和工廠的組合',
    },

    plantFactory: {
      type: `string`,
      sql: `CONCAT(plant, '-', factory)`,
      title: 'Plant-Factory',
      description: '產品線和工廠的組合',
    },

    // ============================================================
    // 分析維度 (基於預計算的使用率)
    // ============================================================
    utilizationLevel: {
      type: `string`,
      sql: `
        CASE 
          WHEN utilization_rate >= 80 THEN 'High (>=80%)'
          WHEN utilization_rate >= 60 THEN 'Medium (60-79%)'
          WHEN utilization_rate >= 40 THEN 'Low (40-59%)'
          WHEN utilization_rate > 0 THEN 'Very Low (1-39%)'
          ELSE 'No Usage (0%)'
        END
      `,
      title: '使用率等級',
      description: '人員使用率等級分類',
    },

    hasActiveUsers: {
      type: `string`,
      sql: `CASE WHEN active_users > 0 THEN 'Has Active Users' ELSE 'No Active Users' END`,
      title: '是否有活躍用戶',
      description: '該維度組合是否有活躍用戶',
    },

    // ============================================================
    // Metadata
    // ============================================================
    lastUpdated: {
      type: `time`,
      sql: `_snapshot_time`,
      title: '快照時間',
      description: '快照建立時間',
    },

    version: {
      type: `number`,
      sql: `_version`,
      title: '版本號',
      description: '快照版本號',
    },
  },

  // ============================================================
  // 預聚合配置 (提升查詢效能) - 基於 Gold 層快照表
  // ============================================================
  preAggregations: {
    // 按日期 + Vx 類型聚合
    dailyVxUtilization: {
      measures: [
        GoldUserUtilization.configUsers,
        GoldUserUtilization.activeUsers,
        GoldUserUtilization.utilizationRate,
      ],
      dimensions: [
        GoldUserUtilization.snapshotDate,
        GoldUserUtilization.vxType,
        GoldUserUtilization.plant,
        GoldUserUtilization.factory,
        GoldUserUtilization.timePeriodType,
      ],
      timeDimension: GoldUserUtilization.snapshotDate,
      granularity: `day`,
      refreshKey: {
        every: `1 hour`,
      },
    },

    // 按 Vx 類型和時間區間聚合
    vxUtilizationSummary: {
      measures: [
        GoldUserUtilization.configUsers,
        GoldUserUtilization.activeUsers,
        GoldUserUtilization.avgConfigUsers,
        GoldUserUtilization.avgActiveUsers,
      ],
      dimensions: [
        GoldUserUtilization.vxType,
        GoldUserUtilization.timePeriodType,
        GoldUserUtilization.utilizationLevel,
      ],
      refreshKey: {
        every: `1 hour`,
      },
    },

    // 按時間區間類型聚合
    timePeriodUtilization: {
      measures: [
        GoldUserUtilization.configUsers,
        GoldUserUtilization.activeUsers,
        GoldUserUtilization.utilizationRate,
      ],
      dimensions: [
        GoldUserUtilization.timePeriodType,
        GoldUserUtilization.timePeriodValue,
        GoldUserUtilization.vxType,
      ],
      refreshKey: {
        every: `30 minutes`,
      },
    },
  },
});