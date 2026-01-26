/**
 * L5 任務執行完成度 Dashboard Cube - 使用維度補齊邏輯
 * 
 * 來源表: gold.l5_dashboard_summary (新的 Gold 層表)
 * 用途: 為 L5 任務執行完成度 Dashboard 提供完整的資料模型
 * 支援: Todo/Doing/Done 分布 + 完成率折線 + 下方明細表
 * 
 * 更新記錄 (2026-01-26):
 * - 使用新的 Gold 層表 gold.l5_dashboard_summary
 * - 基於 Silver 層維度補齊邏輯 (VARINST 優先，MDM 補齊)
 * - 支援 L5 Dashboard 需求規格
 * - 包含製造五階維度和任務狀態指標
 * - 包含維度資料來源追蹤
 * 
 * 維度補齊邏輯:
 * - Region: 主要由 MDM 補齊 (非 V1 流程 VARINST 缺失)
 * - Plant/Factory/Line: 主要來自 VARINST，MDM 作為補齊
 * - 每個維度都有對應的 *_source 欄位標記來源
 */

cube(`L5DashboardCompletion`, {
  sql: `SELECT * FROM gold.l5_dashboard_summary FINAL`,
  
  title: 'L5 任務執行完成度 Dashboard',
  description: '基於維度補齊邏輯的 L5 任務執行完成度儀表板資料模型',

  measures: {
    // ============================================================
    // 🎯 Dashboard 核心指標 - 任務狀態數量 (使用新的欄位名稱)
    // ============================================================
    totalTask: {
      type: `sum`,
      sql: `total_task`,
      title: '任務總數',
      description: '該時間區間內任務總數 (Total Task)',
    },
    
    todoTask: {
      type: `sum`,
      sql: `todo_task`,
      title: 'Todo 任務數',
      description: '尚未開始之任務 (Todo)',
    },
    
    doingTask: {
      type: `sum`,
      sql: `doing_task`,
      title: 'Doing 任務數',
      description: '執行中之任務 (Doing)',
    },

    doneTask: {
      type: `sum`,
      sql: `done_task`,
      title: 'Done 任務數',
      description: '已完成之任務 (Done)',
    },

    // ============================================================
    // 🎯 Dashboard 組合狀態指標 (計算欄位)
    // ============================================================
    doingDoneTask: {
      type: `number`,
      sql: `${doingTask} + ${doneTask}`,
      title: 'Doing + Done 任務數',
      description: '已處理任務總數 (Doing+Done)',
    },

    todoDoingAccTask: {
      type: `number`,
      sql: `${todoTask} + ${doingTask}`,
      title: 'Todo + Doing 任務數',
      description: '尚未完成之累積任務 (Todo+Doing Acc)',
    },

    // ============================================================
    // 🎯 Dashboard 比例指標 (百分比) - 動態計算
    // ============================================================
    todoRate: {
      type: `number`,
      sql: `CASE WHEN ${totalTask} > 0 THEN ${todoTask} * 100.0 / ${totalTask} ELSE 0 END`,
      title: 'Todo 比例 (%)',
      description: 'todo_cnt / total_task × 100%',
      format: `percent`,
    },
    
    doingRate: {
      type: `number`,
      sql: `CASE WHEN ${totalTask} > 0 THEN ${doingTask} * 100.0 / ${totalTask} ELSE 0 END`,
      title: 'Doing 比例 (%)',
      description: 'doing_cnt / total_task × 100%',
      format: `percent`,
    },
    
    doneRate: {
      type: `number`,
      sql: `CASE WHEN ${totalTask} > 0 THEN ${doneTask} * 100.0 / ${totalTask} ELSE 0 END`,
      title: 'Done 比例 (%)',
      description: 'done_cnt / total_task × 100% - 完成率折線圖',
      format: `percent`,
    },
    
    doingDoneRate: {
      type: `number`,
      sql: `CASE WHEN ${totalTask} > 0 THEN ${doingDoneTask} * 100.0 / ${totalTask} ELSE 0 END`,
      title: 'Doing + Done 比例 (%)',
      description: '(doing_cnt + done_cnt) / total_task × 100% - 執行率折線圖',
      format: `percent`,
    },
    
    todoDoingAccRate: {
      type: `number`,
      sql: `CASE WHEN ${totalTask} > 0 THEN ${todoDoingAccTask} * 100.0 / ${totalTask} ELSE 0 END`,
      title: 'Todo + Doing 比例 (%)',
      description: '(todo_cnt + doing_cnt) / total_task × 100% - 累積率折線圖',
      format: `percent`,
    },

    // ============================================================
    // 📊 預計算比例指標 (來自 Gold 層)
    // ============================================================
    preCalculatedCompletionRate: {
      type: `avg`,
      sql: `completion_rate`,
      title: '預計算完成率 (%)',
      description: 'Gold 層預計算的完成率',
      format: `percent`,
    },

    // ============================================================
    // 📊 維度資料來源統計 (新的欄位)
    // ============================================================
    regionMdmBackfillCount: {
      type: `sum`,
      sql: `region_mdm_backfill_count`,
      title: 'Region MDM 補齊數量',
      description: 'Region 維度由 MDM 補齊的任務數量',
    },

    plantMdmBackfillCount: {
      type: `sum`,
      sql: `plant_mdm_backfill_count`,
      title: 'Plant MDM 補齊數量',
      description: 'Plant 維度由 MDM 補齊的任務數量',
    },

    factoryMdmBackfillCount: {
      type: `sum`,
      sql: `factory_mdm_backfill_count`,
      title: 'Factory MDM 補齊數量',
      description: 'Factory 維度由 MDM 補齊的任務數量',
    },

    lineMdmBackfillCount: {
      type: `sum`,
      sql: `line_mdm_backfill_count`,
      title: 'Line MDM 補齊數量',
      description: 'Line 維度由 MDM 補齊的任務數量',
    },
  },

  dimensions: {
    // ============================================================
    // 時間維度 - 基於現有欄位
    // ============================================================
    snapshotDate: {
      type: `time`,
      sql: `snapshot_date`,
      title: '快照日期',
      description: 'L5 指標快照日期',
    },

    // ============================================================
    // 🎯 L5 Dashboard 必要維度 - 基於現有表格欄位
    // ============================================================
    
    // 計算維度：流程團隊 (基於 vx_type)
    flowTeam: {
      type: `string`,
      sql: `CASE 
        WHEN vx_type IN ('V1', 'V2', 'V3') THEN CONCAT(vx_type, '+V1+V2+V3')
        ELSE 'V1+V2+V3'
      END`,
      title: '流程團隊',
      description: '流程團隊（如：V1+V2+V3）- Dashboard 必要維度',
    },

    // Region 維度 (使用補齊後的 region 欄位)
    region: {
      type: `string`,
      sql: `COALESCE(NULLIF(region, ''), 'Unknown')`,
      title: '地區',
      description: '地區（如：CNE）- Dashboard 必要維度，已補齊',
    },

    regionSource: {
      type: `string`,
      sql: `region_source`,
      title: 'Region 資料來源',
      description: 'Region 維度資料來源 (VARINST/MDM)',
    },

    // Plant 維度 (使用補齊後的 plant 欄位)
    plant: {
      type: `string`,
      sql: `COALESCE(NULLIF(plant, ''), 'Unknown')`,
      title: '製造廠區',
      description: '製造廠區（如：WJ2）- Dashboard 必要維度，已補齊',
    },

    plantSource: {
      type: `string`,
      sql: `plant_source`,
      title: 'Plant 資料來源',
      description: 'Plant 維度資料來源 (VARINST/MDM)',
    },

    // Factory 維度 (使用補齊後的 factory 欄位)
    factory: {
      type: `string`,
      sql: `COALESCE(NULLIF(factory, ''), 'Unknown')`,
      title: '製造產品廠',
      description: '製造產品廠（如：NBU）- Dashboard 必要維度，已補齊',
    },

    factorySource: {
      type: `string`,
      sql: `factory_source`,
      title: 'Factory 資料來源',
      description: 'Factory 維度資料來源 (VARINST/MDM)',
    },

    // Line 維度 (使用補齊後的 line 欄位)
    line: {
      type: `string`,
      sql: `COALESCE(NULLIF(line, ''), '')`,
      title: '線體',
      description: '線體（如：E5）- Dashboard 必要維度，已補齊，可為空',
    },

    lineSource: {
      type: `string`,
      sql: `line_source`,
      title: 'Line 資料來源',
      description: 'Line 維度資料來源 (VARINST/MDM)',
    },

    // 計算維度：vx_scope (基於 vx_type)
    vxScope: {
      type: `string`,
      sql: `CASE 
        WHEN vx_type = 'V1' THEN 'V1'
        WHEN vx_type = 'V2' THEN 'V2'
        WHEN vx_type = 'V3' THEN 'V3'
        ELSE 'V1+V2+V3'
      END`,
      title: '任務類型範圍',
      description: '任務類型範圍（V1 / V2 / V3 / V1+V2+V3）- Dashboard 必要維度',
    },

    // 原始 vx_type 維度
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
      description: 'Vx 子類型',
    },

    // ============================================================
    // 時間組合維度 - 用於 Dashboard 時間層級支援
    // ============================================================
    timeLevel: {
      type: `string`,
      sql: `'Day'`,
      title: '時間層級',
      description: 'Day (現有表格只支援日層級)',
    },

    timeValue: {
      type: `string`,
      sql: `toString(snapshot_date)`,
      title: '時間值',
      description: '時間層級對應的值 (日期格式)',
    },

    timeDisplay: {
      type: `string`,
      sql: `CONCAT('Day: ', toString(snapshot_date))`,
      title: '時間顯示',
      description: '時間層級和值的組合顯示',
    },

    // ============================================================
    // 組合維度 - 用於 Dashboard 分組顯示
    // ============================================================
    locationPath: {
      type: `string`,
      sql: `CONCAT(
        COALESCE(NULLIF(region, ''), 'Unknown'), '-',
        COALESCE(NULLIF(plant, ''), 'Unknown'), '-',
        COALESCE(NULLIF(factory, ''), 'Unknown')
      )`,
      title: '位置路徑',
      description: 'Region-Plant-Factory 組合維度',
    },

    fullLocationPath: {
      type: `string`,
      sql: `CONCAT(
        COALESCE(NULLIF(region, ''), 'Unknown'), '-',
        COALESCE(NULLIF(plant, ''), 'Unknown'), '-',
        COALESCE(NULLIF(factory, ''), 'Unknown'),
        CASE WHEN COALESCE(NULLIF(line, ''), '') != '' 
             THEN CONCAT('-', line)
             ELSE '' END
      )`,
      title: '完整位置路徑',
      description: '包含 Line 的完整位置路徑',
    },

    // ============================================================
    // 維度資料來源 (現有欄位)
    // ============================================================
    dimensionSource: {
      type: `string`,
      sql: `dimension_source`,
      title: '維度資料來源',
      description: 'MDM_PRIMARY / FLOWABLE_FALLBACK / NO_DIMENSION',
    },

    // ============================================================
    // Dashboard 篩選維度
    // ============================================================
    regionPlant: {
      type: `string`,
      sql: `CONCAT(
        COALESCE(NULLIF(region, ''), 'Unknown'), '|',
        COALESCE(NULLIF(plant, ''), 'Unknown')
      )`,
      title: 'Region-廠區',
      description: 'Region 和廠區的組合維度，用於篩選',
    },

    plantFactory: {
      type: `string`,
      sql: `CONCAT(
        COALESCE(NULLIF(plant, ''), 'Unknown'), '|',
        COALESCE(NULLIF(factory, ''), 'Unknown')
      )`,
      title: '廠區-工廠',
      description: '廠區和工廠的組合維度，用於篩選',
    },

    factoryLine: {
      type: `string`,
      sql: `CONCAT(
        COALESCE(NULLIF(factory, ''), 'Unknown'), '|',
        COALESCE(NULLIF(line, ''), 'ALL')
      )`,
      title: '工廠-產線',
      description: '工廠和產線的組合維度，用於篩選',
    },

    // ============================================================
    // Metadata
    // ============================================================
    lastUpdated: {
      type: `time`,
      sql: `_update_time`,
      title: '最後更新時間',
      description: 'Gold 表最後更新時間',
    },
  },

  // ============================================================
  // 預聚合配置已移除 - ClickHouse 不支援無索引的 preAggregations
  // 直接查詢 Gold 表效能已足夠
  // ============================================================
  // preAggregations: {
  //   // 已移除：ClickHouse 需要索引支援才能使用 preAggregations
  // },
});