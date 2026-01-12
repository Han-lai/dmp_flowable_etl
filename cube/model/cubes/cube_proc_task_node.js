// ============================================
// Cube: ProcTaskNode (任務節點)
// 來源: silver.RMV_HI_PROC_TASK_NODE
// Grain: 一個 TASK_ID = 一列
// 層級: Semantic Gold (核心指標) + Silver 包裝 (輔助指標)
// ============================================

cube(`ProcTaskNode`, {
  sql: `
    SELECT 
      TASK_ID,
      PROC_INST_ID,
      PROC_DEF_NAME,
      BUSINESS_KEY,
      TASK_NAME,
      TASK_STATUS,
      ASSIGNEE,
      DEPT_NAME,
      FACTORY,
      PLANT,
      LINE_NAME,
      REGION,
      START_TIME,
      END_TIME,
      CLAIM_TIME,
      IDLE_DURATION_SEC,
      WORK_DURATION_SEC,
      TOTAL_DURATION_SEC
    FROM silver.RMV_HI_PROC_TASK_NODE
  `,

  title: '任務節點',
  description: '流程任務的詳細資訊，包含狀態、時長、指派人員等。此為任務層級分析的權威來源。',

  // ============================================
  // Dimensions (維度)
  // ============================================
  dimensions: {
    taskId: {
      sql: `TASK_ID`,
      type: `string`,
      primaryKey: true,
      title: '任務 ID',
    },
    procInstId: {
      sql: `PROC_INST_ID`,
      type: `string`,
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
    taskName: {
      sql: `TASK_NAME`,
      type: `string`,
      title: '任務名稱',
    },
    taskStatus: {
      sql: `TASK_STATUS`,
      type: `string`,
      title: '任務狀態',
      description: 'TODO / DOING / DONE / DONE_AUTO / CANCELLED',
    },
    assignee: {
      sql: `ASSIGNEE`,
      type: `string`,
      title: '指派人員',
    },
    deptName: {
      sql: `DEPT_NAME`,
      type: `string`,
      title: '部門名稱',
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
    claimTime: {
      sql: `CLAIM_TIME`,
      type: `time`,
      title: '認領時間',
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
     * 在途任務總數
     * 
     * 【定義】狀態為 TODO 或 DOING 的任務數量
     * 【業務語意】反映系統中待處理的工作量
     * 【合法維度】plant, factory, lineName, deptName, assignee, procDefName
     * 【禁止維度】taskId, procInstId, businessKey (會導致無意義的 1:1 結果)
     * 【時間維度】不適用 (快照指標，不可做時間序列)
     * 【聚合方式】可跨維度 SUM
     */
    inProgressTaskCount: {
      sql: `TASK_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.TASK_STATUS IN ('TODO', 'DOING')` }],
      title: '🥇 在途任務數',
      description: `【Gold 指標】狀態為 TODO 或 DOING 的任務數量。
合法維度: plant, factory, lineName, deptName, assignee, procDefName
禁止維度: taskId, procInstId, businessKey
時間維度: 不適用 (快照指標)
聚合方式: 可跨維度 SUM`,
    },

    /**
     * 自動完成率
     * 
     * 【定義】DONE_AUTO / (DONE + DONE_AUTO) × 100%
     * 【業務語意】反映流程自動化程度
     * 【合法維度】plant, factory, procDefName
     * 【禁止維度】assignee (自動完成無指派人員)
     * 【時間維度】endTime (week/month)
     * 【聚合方式】⚠️ 不可直接平均，需用 doneAutoForRate / doneTotalForRate 重算
     */
    autoCompleteRate: {
      sql: `${doneAutoForRate} * 100.0 / NULLIF(${doneTotalForRate}, 0)`,
      type: `number`,
      title: '🥇 自動完成率 (%)',
      description: `【Gold 指標】DONE_AUTO / (DONE + DONE_AUTO) × 100%
合法維度: plant, factory, procDefName
禁止維度: assignee
時間維度: endTime (week/month)
⚠️ 聚合警告: 不可直接平均！跨維度聚合需用 doneAutoForRate / doneTotalForRate 重新計算`,
    },

    /**
     * 平均任務處理時長 (秒)
     * 
     * 【定義】已完成任務 (DONE) 的處理時長平均值
     * 【業務語意】反映人員處理效率
     * 【合法維度】plant, factory, assignee, procDefName, taskName
     * 【時間維度】endTime (week/month)
     * 【聚合方式】⚠️ 不可直接平均，需用 totalWorkDuration / doneCount 重算
     */
    avgWorkDuration: {
      sql: `WORK_DURATION_SEC`,
      type: `avg`,
      filters: [{ sql: `${CUBE}.TASK_STATUS = 'DONE'` }],
      title: '🥇 平均任務處理時長 (秒)',
      description: `【Gold 指標】已完成任務 (DONE) 的處理時長平均值
合法維度: plant, factory, assignee, procDefName, taskName
時間維度: endTime (week/month)
⚠️ 聚合警告: 不可直接平均！跨維度聚合需用 totalWorkDuration / doneCount 重新計算`,
    },

    // ==========================================
    // 🥈 SILVER 包裝 - 輔助指標 (internal)
    // ==========================================

    // 狀態分布 - 供前端組合使用
    todoCount: {
      sql: `TASK_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.TASK_STATUS = 'TODO'` }],
      title: '🥈 TODO 任務數 (internal)',
      description: '【Silver 輔助】狀態分布組件，供前端組合使用',
    },
    doingCount: {
      sql: `TASK_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.TASK_STATUS = 'DOING'` }],
      title: '🥈 DOING 任務數 (internal)',
      description: '【Silver 輔助】狀態分布組件，供前端組合使用',
    },
    doneCount: {
      sql: `TASK_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.TASK_STATUS = 'DONE'` }],
      title: '🥈 DONE 任務數 (internal)',
      description: '【Silver 輔助】狀態分布組件，供前端組合使用',
    },
    doneAutoCount: {
      sql: `TASK_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.TASK_STATUS = 'DONE_AUTO'` }],
      title: '🥈 DONE_AUTO 任務數 (internal)',
      description: '【Silver 輔助】狀態分布組件，供前端組合使用',
    },
    cancelledCount: {
      sql: `TASK_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.TASK_STATUS = 'CANCELLED'` }],
      title: '🥈 CANCELLED 任務數 (internal)',
      description: '【Silver 輔助】狀態分布組件，供前端組合使用',
    },

    // 自動完成率的分子分母 - 供跨維度重算
    doneAutoForRate: {
      sql: `TASK_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.TASK_STATUS = 'DONE_AUTO'` }],
      title: '🥈 自動完成數 (分子)',
      description: '【Silver 輔助】autoCompleteRate 的分子，供跨維度重算使用',
    },
    doneTotalForRate: {
      sql: `TASK_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.TASK_STATUS IN ('DONE', 'DONE_AUTO')` }],
      title: '🥈 完成總數 (分母)',
      description: '【Silver 輔助】autoCompleteRate 的分母，供跨維度重算使用',
    },

    // 處理時長的總和與計數 - 供跨維度重算
    totalWorkDuration: {
      sql: `WORK_DURATION_SEC`,
      type: `sum`,
      filters: [{ sql: `${CUBE}.TASK_STATUS = 'DONE'` }],
      title: '🥈 處理時長總和 (秒)',
      description: '【Silver 輔助】avgWorkDuration 的分子，供跨維度重算使用',
    },

    // 閒置時長
    avgIdleDuration: {
      sql: `IDLE_DURATION_SEC`,
      type: `avg`,
      title: '🥈 平均閒置時長 (秒)',
      description: '【Silver 輔助】任務建立到認領的平均時長',
    },
  },
});
