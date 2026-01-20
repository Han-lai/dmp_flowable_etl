// ============================================
// Cube: BizEventInfo (業務事件) - 已停用
// 原因: L5 指標不需要業務事件層級分析
// 狀態: 暫時停用，如需要可重新啟用
// ============================================

/*
cube(`BizEventInfo`, {
  sql: `
    SELECT 
      BIZ_EVENT_KEY,
      FIRST_PROC_DEF_NAME,
      FIRST_START_TIME,
      FINAL_END_TIME,
      IS_IN_PROGRESS,
      TOTAL_DURATION_SEC,
      PROCESS_COUNT
    FROM silver.RMV_HI_BIZ_EVENT_INFO
  `,

  title: '業務事件',
  description: '業務事件的聚合資訊。此為業務事件層級分析的權威來源。⚠️ 注意：此 Cube 沒有廠區維度 (plant/factory/lineName)。',

  // ============================================
  // Dimensions (維度)
  // ============================================
  dimensions: {
    bizEventKey: {
      sql: `BIZ_EVENT_KEY`,
      type: `string`,
      primaryKey: true,
      title: '業務事件 Key',
    },
    firstProcDefName: {
      sql: `FIRST_PROC_DEF_NAME`,
      type: `string`,
      title: '首個流程定義名稱',
    },
    firstStartTime: {
      sql: `FIRST_START_TIME`,
      type: `time`,
      title: '首個任務開始時間',
    },
    finalEndTime: {
      sql: `FINAL_END_TIME`,
      type: `time`,
      title: '最後任務結束時間',
    },
    isInProgress: {
      sql: `IS_IN_PROGRESS`,
      type: `number`,
      title: '是否在途',
    },
  },

  // ============================================
  // Measures (指標)
  // ============================================
  measures: {
    // ==========================================
    // 🥇 GOLD 指標 - 核心業務指標
    // ==========================================

    /**
     * 在途業務事件數
     * 
     * 【定義】尚未完成的業務事件數量
     * 【業務語意】反映系統中正在處理的業務量
     * 【合法維度】firstProcDefName
     * 【禁止維度】bizEventKey (會導致無意義的 1:1 結果)
     * 【時間維度】不適用 (快照指標)
     * 【聚合方式】可跨維度 SUM
     * ⚠️ 注意：此 Cube 沒有廠區維度，如需按廠區分析請用 ProcTaskNode
     */
    inProgressEventCount: {
      sql: `BIZ_EVENT_KEY`,
      type: `count`,
      filters: [{ sql: `${CUBE}.IS_IN_PROGRESS = 1` }],
      title: '🥇 在途業務事件數',
      description: `【Gold 指標】尚未完成的業務事件數量
合法維度: firstProcDefName
禁止維度: bizEventKey
時間維度: 不適用 (快照指標)
聚合方式: 可跨維度 SUM
⚠️ 注意: 此 Cube 沒有廠區維度，如需按廠區分析請用 ProcTaskNode`,
    },

    /**
     * 平均業務事件總歷時 (秒)
     * 
     * 【定義】已完成業務事件的總歷時平均值
     * 【業務語意】反映業務流程整體效率
     * 【合法維度】firstProcDefName
     * 【時間維度】finalEndTime (week/month)
     * 【聚合方式】⚠️ 不可直接平均，需用 totalDurationSum / completedEventCount 重算
     */
    avgTotalDuration: {
      sql: `TOTAL_DURATION_SEC`,
      type: `avg`,
      filters: [{ sql: `${CUBE}.IS_IN_PROGRESS = 0` }],
      title: '🥇 平均業務事件總歷時 (秒)',
      description: `【Gold 指標】已完成業務事件的總歷時平均值
合法維度: firstProcDefName
時間維度: finalEndTime (week/month)
⚠️ 聚合警告: 不可直接平均！跨維度聚合需用 totalDurationSum / completedEventCount 重新計算`,
    },

    // ==========================================
    // 🥈 SILVER 包裝 - 輔助指標 (internal)
    // ==========================================

    completedEventCount: {
      sql: `BIZ_EVENT_KEY`,
      type: `count`,
      filters: [{ sql: `${CUBE}.IS_IN_PROGRESS = 0` }],
      title: '🥈 已完成業務事件數 (internal)',
      description: '【Silver 輔助】avgTotalDuration 的分母，供跨維度重算使用',
    },

    totalDurationSum: {
      sql: `TOTAL_DURATION_SEC`,
      type: `sum`,
      filters: [{ sql: `${CUBE}.IS_IN_PROGRESS = 0` }],
      title: '🥈 總歷時總和 (秒)',
      description: '【Silver 輔助】avgTotalDuration 的分子，供跨維度重算使用',
    },
  },
});

// 停用原因: L5 指標專注於任務層級分析，不需要業務事件聚合
// 如需重新啟用，請移除註解並確認資料來源 silver.RMV_HI_BIZ_EVENT_INFO 存在
*/
