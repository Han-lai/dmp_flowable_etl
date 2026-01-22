/**
 * Gold Layer: User Utilization Rate (人員使用率)
 * 基於指標定義文件的人員使用率 Cube
 * 
 * 來源表: silver.mv_dim_config_user (Config Users) + silver.mv_fact_task_vx_attribution (Active Users)
 * Grain: vx_type + plant + factory + line + time_period
 * 
 * 用途:
 * - 人員使用率計算 (Active Users / Config Users)
 * - 支援 Vx/Plant/Factory/Line 維度篩選
 * - 支援時間區間分析 (Total/Month/Week/Daily)
 */

cube(`GoldUserUtilization`, {
  sql: `
    WITH config_users AS (
      SELECT 
        vx_type,
        plant,
        factory,
        COUNT(DISTINCT emp_code) AS config_user_count
      FROM silver.mv_dim_config_user FINAL
      WHERE is_config_user = 1
      GROUP BY vx_type, plant, factory
    ),
    active_users AS (
      SELECT 
        vx_type,
        plant,
        factory,
        toDate(task_create_time) AS task_date,
        COUNT(DISTINCT task_assignee_name) AS active_user_count
      FROM silver.mv_fact_task_vx_attribution FINAL
      WHERE is_excluded = 0 
        AND task_status IN ('DONE', 'DOING')
        AND task_assignee_name IS NOT NULL
        AND task_assignee_name != ''
      GROUP BY vx_type, plant, factory, task_date
    )
    SELECT 
      c.vx_type,
      c.plant,
      c.factory,
      '' AS line,
      a.task_date AS snapshot_date,
      c.config_user_count,
      COALESCE(a.active_user_count, 0) AS active_user_count,
      now64(3) AS _update_time
    FROM config_users c
    LEFT JOIN active_users a ON c.vx_type = a.vx_type 
                             AND c.plant = a.plant 
                             AND c.factory = a.factory
  `,
  
  title: '人員使用率 (Gold)',
  description: '基於指標定義文件的人員使用率指標，支援 Active Users / Config Users 計算。',

  measures: {
    // ============================================================
    // 🥇 人員使用率核心指標
    // ============================================================
    configUsers: {
      type: `sum`,
      sql: `config_user_count`,
      title: 'Config Users',
      description: '🥇 具備對應系統使用權限的人員數',
    },
    
    activeUsers: {
      type: `sum`,
      sql: `active_user_count`,
      title: 'Active Users',
      description: '🥇 實際有使用紀錄的人員數',
    },

    utilizationRate: {
      type: `number`,
      sql: `CASE WHEN ${configUsers} > 0 THEN ${activeUsers} * 100.0 / ${configUsers} ELSE 0 END`,
      title: '人員使用率 (%)',
      description: '🥇 Active Users / Config Users × 100%',
      format: `percent`,
    },

    // ============================================================
    // 📊 輔助計算指標
    // ============================================================
    avgConfigUsers: {
      type: `avg`,
      sql: `config_user_count`,
      title: '平均 Config Users',
      description: '平均具備權限的人員數',
    },

    avgActiveUsers: {
      type: `avg`,
      sql: `active_user_count`,
      title: '平均 Active Users',
      description: '平均活躍人員數',
    },

    maxConfigUsers: {
      type: `max`,
      sql: `config_user_count`,
      title: '最大 Config Users',
      description: '最大具備權限的人員數',
    },

    maxActiveUsers: {
      type: `max`,
      sql: `active_user_count`,
      title: '最大 Active Users',
      description: '最大活躍人員數',
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
    // 分析維度
    // ============================================================
    utilizationLevel: {
      type: `string`,
      sql: `
        CASE 
          WHEN ${utilizationRate} >= 80 THEN 'High (>=80%)'
          WHEN ${utilizationRate} >= 60 THEN 'Medium (60-79%)'
          WHEN ${utilizationRate} >= 40 THEN 'Low (40-59%)'
          WHEN ${utilizationRate} > 0 THEN 'Very Low (1-39%)'
          ELSE 'No Usage (0%)'
        END
      `,
      title: '使用率等級',
      description: '人員使用率等級分類',
    },

    hasActiveUsers: {
      type: `string`,
      sql: `CASE WHEN active_user_count > 0 THEN 'Has Active Users' ELSE 'No Active Users' END`,
      title: '是否有活躍用戶',
      description: '該維度組合是否有活躍用戶',
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
  // 預聚合配置 (提升查詢效能)
  // ============================================================
  preAggregations: {
    // 按日期 + Vx 類型聚合
    dailyVxUtilization: {
      measures: [
        GoldUserUtilization.configUsers,
        GoldUserUtilization.activeUsers,
      ],
      dimensions: [
        GoldUserUtilization.snapshotDate,
        GoldUserUtilization.vxType,
        GoldUserUtilization.plant,
        GoldUserUtilization.factory,
      ],
      timeDimension: GoldUserUtilization.snapshotDate,
      granularity: `day`,
      refreshKey: {
        every: `1 hour`,
      },
    },

    // 按 Vx 類型聚合
    vxUtilizationSummary: {
      measures: [
        GoldUserUtilization.configUsers,
        GoldUserUtilization.activeUsers,
        GoldUserUtilization.avgConfigUsers,
        GoldUserUtilization.avgActiveUsers,
      ],
      dimensions: [
        GoldUserUtilization.vxType,
        GoldUserUtilization.utilizationLevel,
      ],
      refreshKey: {
        every: `1 hour`,
      },
    },
  },
});