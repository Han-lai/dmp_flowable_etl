/**
 * Gold Layer: L5 Task Completion Snapshot (基於 MDM 整合 MVIEW 架構)
 * L5 任務完成率快照 - 基於 gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
 * 
 * 來源表: gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV (MDM 整合版本)
 * 資料來源: silver.mv_l5_metrics_realtime_mdm (MDM 整合邏輯)
 * Grain: snapshot_date + region + plant + factory + line + vx_type + dimension_source
 * 
 * 更新記錄 (2026-01-23):
 * - 整合 MDM 主檔表提供完整五階維度支援
 * - 解決 V2/V3 維度缺失問題
 * - 新增 Region 層級維度
 * - 支援維度資料來源追蹤 (MDM_PRIMARY/FLOWABLE_FALLBACK/NO_DIMENSION)
 * - 315% 工單規則使用 LIKE '315%' 
 * - V1/V3 歸屬邏輯：工單號規則優先級最高
 * 
 * 用途:
 * - L5 指標歷史趨勢查詢
 * - 任務完成率回溯分析
 * - 完整五階維度聚合
 * - 維度資料品質監控
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
      sql: `0`,  // MDM 版本暫時沒有 excluded_qty
      title: 'L5 排除任務數',
      description: 'L5 指標 - 被排除的任務數量 (MDM 版本暫不支援)',
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
    // 📊 維度資料來源統計 (MDM 整合版本新增)
    // ============================================================
    mdmPrimaryTasks: {
      type: `sum`,
      sql: `sum_mdm_primary_qty`,
      title: 'MDM 主來源任務數',
      description: '完全來自 MDM 主檔表的任務數量',
    },

    flowableFallbackTasks: {
      type: `sum`,
      sql: `sum_flowable_fallback_qty`,
      title: 'Flowable 輔助來源任務數',
      description: '使用 Flowable 變數作為 fallback 的任務數量',
    },

    noDimensionTasks: {
      type: `sum`,
      sql: `sum_no_dimension_qty`,
      title: '無維度任務數',
      description: '無法取得維度資料的任務數量',
    },

    // ============================================================
    // 📊 排除原因統計 (部分支援)
    // ============================================================
    bypassTasks: {
      type: `sum`,
      sql: `sum_bypass_qty`,
      title: '旁路任務數',
      description: 'TaskBypass != N 的任務數量',
    },

    ePrefixTasks: {
      type: `sum`,
      sql: `0`,  // MDM 版本暫時沒有這些統計
      title: 'E 前綴任務數',
      description: 'TaskDefinitionKey 以 E 開頭的任務數量 (MDM 版本暫不支援)',
    },

    cPrefixTasks: {
      type: `sum`,
      sql: `0`,  // MDM 版本暫時沒有這些統計
      title: 'C 前綴任務數',
      description: 'TaskDefinitionKey 以 C 開頭的任務數量 (MDM 版本暫不支援)',
    },

    qOrderTasks: {
      type: `sum`,
      sql: `0`,  // MDM 版本暫時沒有這些統計
      title: 'Q 工單任務數',
      description: '工單號以 Q 開頭的任務數量 (MDM 版本暫不支援)',
    },

    rOrderTasks: {
      type: `sum`,
      sql: `0`,  // MDM 版本暫時沒有這些統計
      title: 'R 工單任務數',
      description: '工單號以 R 開頭的任務數量 (MDM 版本暫不支援)',
    },

    specialV1RuleTasks: {
      type: `sum`,
      sql: `0`,  // MDM 版本暫時沒有這些統計
      title: '特殊 V1 規則任務數',
      description: '套用工單號規則的 V1 任務數量 (MDM 版本暫不支援)',
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
      description: 'MDM 版本暫時沒有子類型',
    },

    // ============================================================
    // 完整五階維度 (MDM 整合版本)
    // ============================================================
    regionCode: {
      type: `string`,
      sql: `region_code`,
      title: 'Region 代碼',
      description: 'Region 層級代碼 (MDM 整合新增)',
    },

    regionName: {
      type: `string`,
      sql: `region_name`,
      title: 'Region 名稱',
      description: 'Region 層級名稱 (MDM 整合新增)',
    },

    plantCode: {
      type: `string`,
      sql: `plant_code`,
      title: '廠區代碼',
      description: '廠區代碼 (MDM 主來源)',
    },

    plantName: {
      type: `string`,
      sql: `plant_name`,
      title: '廠區名稱',
      description: '廠區名稱 (MDM 主來源)',
    },

    factoryCode: {
      type: `string`,
      sql: `factory_code`,
      title: '工廠代碼',
      description: '工廠代碼 (MDM 主來源)',
    },

    factoryName: {
      type: `string`,
      sql: `factory_name`,
      title: '工廠名稱',
      description: '工廠名稱 (MDM 主來源)',
    },

    lineCode: {
      type: `string`,
      sql: `line_code`,
      title: '產線代碼',
      description: '產線代碼 (MDM 主來源)',
    },

    lineName: {
      type: `string`,
      sql: `line_name`,
      title: '產線名稱',
      description: '產線名稱 (MDM 主來源)',
    },

    // ============================================================
    // 相容性維度欄位 (保持向後相容)
    // ============================================================
    plant: {
      type: `string`,
      sql: `plant`,
      title: '廠區 (相容)',
      description: '廠區代碼 (相容性欄位)',
    },
    
    factory: {
      type: `string`,
      sql: `factory`,
      title: '工廠 (相容)',
      description: '工廠代碼 (相容性欄位)',
    },

    line: {
      type: `string`,
      sql: `line`,
      title: '產線 (相容)',
      description: '產線代碼 (相容性欄位)',
    },

    // ============================================================
    // 維度資料來源 (MDM 整合版本新增)
    // ============================================================
    dimensionSource: {
      type: `string`,
      sql: `dimension_source`,
      title: '維度資料來源',
      description: 'MDM_PRIMARY / FLOWABLE_FALLBACK / NO_DIMENSION',
    },

    // ============================================================
    // 組合維度 (用於分組)
    // ============================================================
    regionPlant: {
      type: `string`,
      sql: `CONCAT(region_code, '|', plant_code)`,
      title: 'Region-廠區',
      description: 'Region 和廠區的組合維度',
    },

    plantFactory: {
      type: `string`,
      sql: `CONCAT(plant_code, '|', factory_code)`,
      title: '廠區-工廠',
      description: '廠區和工廠的組合維度',
    },

    factoryLine: {
      type: `string`,
      sql: `CONCAT(factory_code, '|', line_code)`,
      title: '工廠-產線',
      description: '工廠和產線的組合維度',
    },

    vxTypeSubtype: {
      type: `string`,
      sql: `CONCAT(vx_type, CASE WHEN vx_subtype != '' THEN CONCAT('_', vx_subtype) ELSE '' END)`,
      title: 'Vx 完整類型',
      description: 'Vx 類型和子類型的組合 (MDM 版本暫無子類型)',
    },

    fullDimensionPath: {
      type: `string`,
      sql: `CONCAT(region_code, '>', plant_code, '>', factory_code, '>', line_code)`,
      title: '完整維度路徑',
      description: '完整五階維度路徑 (Region>Plant>Factory>Line)',
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
  // 預聚合配置 (提升查詢效能) - MDM 整合版本
  // ============================================================
  preAggregations: {
    // 按日期 + Vx 類型聚合
    dailyVxSummary: {
      measures: [
        GoldL5TaskCompletion.totalTasks,
        GoldL5TaskCompletion.doneTasks,
        GoldL5TaskCompletion.doingTasks,
        GoldL5TaskCompletion.todoTasks,
        GoldL5TaskCompletion.mdmPrimaryTasks,
        GoldL5TaskCompletion.flowableFallbackTasks,
        GoldL5TaskCompletion.noDimensionTasks,
      ],
      dimensions: [
        GoldL5TaskCompletion.snapshotDate,
        GoldL5TaskCompletion.vxType,
        GoldL5TaskCompletion.dimensionSource,
      ],
      timeDimension: GoldL5TaskCompletion.snapshotDate,
      granularity: `day`,
      refreshKey: {
        every: `1 hour`,
      },
    },

    // 按完整五階維度聚合
    fullDimensionSummary: {
      measures: [
        GoldL5TaskCompletion.totalTasks,
        GoldL5TaskCompletion.doneTasks,
        GoldL5TaskCompletion.inProgressTasks,
      ],
      dimensions: [
        GoldL5TaskCompletion.snapshotDate,
        GoldL5TaskCompletion.regionCode,
        GoldL5TaskCompletion.plantCode,
        GoldL5TaskCompletion.factoryCode,
        GoldL5TaskCompletion.lineCode,
        GoldL5TaskCompletion.vxType,
      ],
      timeDimension: GoldL5TaskCompletion.snapshotDate,
      granularity: `day`,
      refreshKey: {
        every: `1 hour`,
      },
    },

    // 維度資料來源品質監控
    dimensionQualitySummary: {
      measures: [
        GoldL5TaskCompletion.mdmPrimaryTasks,
        GoldL5TaskCompletion.flowableFallbackTasks,
        GoldL5TaskCompletion.noDimensionTasks,
      ],
      dimensions: [
        GoldL5TaskCompletion.snapshotDate,
        GoldL5TaskCompletion.dimensionSource,
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