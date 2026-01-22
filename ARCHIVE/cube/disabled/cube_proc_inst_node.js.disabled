// ============================================
// Cube: ProcInstNode (流程實例) - 已停用
// 原因: L5 指標不需要流程實例層級分析
// 狀態: 暫時停用，如需要可重新啟用
// ============================================

/*
cube(`ProcInstNode`, {
  sql: `
    SELECT 
      PROC_INST_ID,
      BUSINESS_KEY,
      PROC_DEF_NAME,
      DEPTH,
      SUPER_ID,
      FACTORY,
      PLANT,
      LINE_NAME,
      REGION,
      PROC_STATE,
      IS_COMPLETED,
      START_TIME,
      END_TIME,
      DURATION_SEC
    FROM silver.RMV_HI_PROCINST_NODE
  `,

  title: '流程實例',
  description: '流程實例的詳細資訊。此為流程層級分析的權威來源。',

  // ============================================
  // Dimensions (維度)
  // ============================================
  dimensions: {
    procInstId: {
      sql: `PROC_INST_ID`,
      type: `string`,
      primaryKey: true,
      title: '流程實例 ID',
    },
    procDefName: {
      sql: `PROC_DEF_NAME`,
      type: `string`,
      title: '流程定義名稱',
    },
    businessKey: {
      sql: `BUSINESS_KEY`,
      type: `string`,
      title: '業務事件 Key',
    },
    depth: {
      sql: `DEPTH`,
      type: `number`,
      title: '流程深度',
      description: '1=主流程, 2=子流程',
    },
    superId: {
      sql: `SUPER_ID`,
      type: `string`,
      title: '父流程 ID',
    },
    factory: {
      sql: `FACTORY`,
      type: `string`,
      title: '工廠',
    },
    plant: {
      sql: `PLANT`,
      type: `string`,
      title: '產品線',
    },
    lineName: {
      sql: `LINE_NAME`,
      type: `string`,
      title: '線別',
    },
    region: {
      sql: `REGION`,
      type: `string`,
      title: '地區',
    },
    procState: {
      sql: `PROC_STATE`,
      type: `string`,
      title: '流程狀態',
    },
    isCompleted: {
      sql: `IS_COMPLETED`,
      type: `number`,
      title: '是否完成',
    },
    startTime: {
      sql: `START_TIME`,
      type: `time`,
      title: '開始時間',
    },
    endTime: {
      sql: `END_TIME`,
      type: `time`,
      title: '結束時間',
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
     * 在途流程數
     * 
     * 【定義】尚未完成的流程實例數量
     * 【業務語意】反映系統中正在執行的流程量
     * 【合法維度】plant, factory, procDefName, depth
     * 【禁止維度】procInstId, businessKey
     * 【時間維度】不適用 (快照指標)
     * 【聚合方式】可跨維度 SUM
     */
    inProgressCount: {
      sql: `PROC_INST_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.IS_COMPLETED = 0` }],
      title: '🥇 在途流程數',
      description: `【Gold 指標】尚未完成的流程實例數量
合法維度: plant, factory, procDefName, depth
禁止維度: procInstId, businessKey
時間維度: 不適用 (快照指標)
聚合方式: 可跨維度 SUM`,
    },

    /**
     * 已完成流程數
     * 
     * 【定義】已完成的流程實例數量
     * 【業務語意】反映系統處理完成的流程量
     * 【合法維度】plant, factory, procDefName, depth
     * 【時間維度】endTime (day/week/month)
     * 【聚合方式】可跨維度 SUM
     */
    completedCount: {
      sql: `PROC_INST_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.IS_COMPLETED = 1` }],
      title: '🥇 已完成流程數',
      description: `【Gold 指標】已完成的流程實例數量
合法維度: plant, factory, procDefName, depth
時間維度: endTime (day/week/month)
聚合方式: 可跨維度 SUM`,
    },

    // ==========================================
    // 🥈 SILVER 包裝 - 輔助指標 (internal)
    // ==========================================

    mainProcCount: {
      sql: `PROC_INST_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.DEPTH = 1` }],
      title: '🥈 主流程數 (internal)',
      description: '【Silver 輔助】DEPTH = 1 的流程數',
    },

    subProcCount: {
      sql: `PROC_INST_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.DEPTH = 2` }],
      title: '🥈 子流程數 (internal)',
      description: '【Silver 輔助】DEPTH = 2 的流程數',
    },

    avgDuration: {
      sql: `DURATION_SEC`,
      type: `avg`,
      filters: [{ sql: `${CUBE}.IS_COMPLETED = 1` }],
      title: '🥈 平均流程時長 (秒)',
      description: `【Silver 輔助】已完成流程的平均時長
⚠️ 聚合警告: 不可直接平均！跨維度聚合需用 totalDuration / completedCount 重新計算`,
    },

    totalDuration: {
      sql: `DURATION_SEC`,
      type: `sum`,
      filters: [{ sql: `${CUBE}.IS_COMPLETED = 1` }],
      title: '🥈 流程時長總和 (秒)',
      description: '【Silver 輔助】avgDuration 的分子，供跨維度重算使用',
    },
  },
});

// 停用原因: L5 指標專注於任務層級分析，不需要流程實例聚合
// 如需重新啟用，請移除註解並確認資料來源 silver.RMV_HI_PROCINST_NODE 存在
*/
