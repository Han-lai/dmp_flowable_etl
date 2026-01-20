// ============================================
// Cube: ProcTaskNode (任務節點) - L5 指標專用
// 來源: silver.FACT_TASK_VX_ATTRIBUTION
// Grain: 一個 task_id = 一列
// 層級: L5 任務完成率指標的核心 Cube
// ============================================

cube(`ProcTaskNode`, {
  sql: `
    SELECT 
      task_id,
      task_create_date,
      task_create_time,
      task_claim_time,
      task_end_time,
      task_status,
      task_bypass,
      task_definition_key,
      task_name,
      task_assignee_name,
      task_assignee_account,
      vx_type,
      vx_subtype,
      is_excluded,
      plant,
      factory,
      line,
      proc_inst_id,
      business_key,
      mo_number
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
  `,

  title: 'L5 任務指標',
  description: 'L5 任務執行完成率指標的核心 Cube。基於 FACT_TASK_VX_ATTRIBUTION 提供即時任務查詢能力。',

  // ============================================
  // Dimensions (維度)
  // ============================================
  dimensions: {
    taskId: {
      sql: `task_id`,
      type: `string`,
      primaryKey: true,
      title: '任務 ID',
    },
    procInstId: {
      sql: `proc_inst_id`,
      type: `string`,
      title: '流程實例 ID',
    },
    businessKey: {
      sql: `business_key`,
      type: `string`,
      title: '業務事件 Key',
    },
    taskName: {
      sql: `task_name`,
      type: `string`,
      title: '任務名稱',
    },
    taskStatus: {
      sql: `task_status`,
      type: `string`,
      title: '任務狀態',
      description: 'TODO / DOING / DONE',
    },
    taskBypass: {
      sql: `task_bypass`,
      type: `string`,
      title: '任務略過',
      description: 'Y=略過, N=正常',
    },
    taskDefinitionKey: {
      sql: `task_definition_key`,
      type: `string`,
      title: '任務定義 Key',
    },
    assigneeName: {
      sql: `task_assignee_name`,
      type: `string`,
      title: '指派人員',
    },
    assigneeAccount: {
      sql: `task_assignee_account`,
      type: `string`,
      title: '指派帳號',
    },
    vxType: {
      sql: `vx_type`,
      type: `string`,
      title: 'Vx 類型',
      description: 'V1 / V2 / V3',
    },
    vxSubtype: {
      sql: `vx_subtype`,
      type: `string`,
      title: 'Vx 子類型',
      description: 'V1_NPE / V1_MFG',
    },
    isExcluded: {
      sql: `is_excluded`,
      type: `number`,
      title: '是否排除',
      description: '1=排除, 0=包含',
    },
    plant: {
      sql: `plant`,
      type: `string`,
      title: '廠區',
    },
    factory: {
      sql: `factory`,
      type: `string`,
      title: '工廠',
    },
    line: {
      sql: `line`,
      type: `string`,
      title: '產線',
    },
    moNumber: {
      sql: `mo_number`,
      type: `string`,
      title: '工單號',
    },
    taskCreateDate: {
      sql: `task_create_date`,
      type: `time`,
      title: '任務建立日期',
    },
    taskCreateTime: {
      sql: `task_create_time`,
      type: `time`,
      title: '任務建立時間',
    },
    taskClaimTime: {
      sql: `task_claim_time`,
      type: `time`,
      title: '任務認領時間',
    },
    taskEndTime: {
      sql: `task_end_time`,
      type: `time`,
      title: '任務結束時間',
    },
  },

  // ============================================
  // Measures (指標)
  // ============================================
  measures: {
    // ==========================================
    // 🥇 L5 核心指標
    // ==========================================

    /**
     * L5 在途任務數 (排除測試任務)
     * 
     * 【定義】狀態為 TODO 或 DOING 且未被排除的任務數量
     * 【業務語意】L5 指標的核心 - 實際在途工作量
     * 【合法維度】plant, factory, line, vxType, assigneeName
     * 【排除邏輯】is_excluded = 0 (排除 bypass、測試工單等)
     */
    l5InProgressTaskCount: {
      sql: `task_id`,
      type: `count`,
      filters: [
        { sql: `${CUBE}.task_status IN ('TODO', 'DOING')` },
        { sql: `${CUBE}.is_excluded = 0` }
      ],
      title: '🥇 L5 在途任務數',
      description: `【L5 核心指標】狀態為 TODO 或 DOING 且未被排除的任務數量。
合法維度: plant, factory, line, vxType, assigneeName
排除邏輯: is_excluded = 0`,
    },

    /**
     * L5 任務完成率
     * 
     * 【定義】已完成任務數 / 總任務數 × 100%
     * 【業務語意】L5 指標的核心 - 任務執行效率
     * 【計算邏輯】基於未排除的任務計算
     */
    l5TaskCompletionRate: {
      sql: `CASE WHEN ${l5TotalTaskCount} > 0 THEN ${l5DoneTaskCount} * 100.0 / ${l5TotalTaskCount} ELSE 0 END`,
      type: `number`,
      title: '🥇 L5 任務完成率 (%)',
      description: '【L5 核心指標】已完成任務數 / 總任務數 × 100%',
      format: `percent`,
    },

    // ==========================================
    // 🥈 L5 輔助指標 (分子分母)
    // ==========================================

    l5TotalTaskCount: {
      sql: `task_id`,
      type: `count`,
      filters: [{ sql: `${CUBE}.is_excluded = 0` }],
      title: '🥈 L5 總任務數',
      description: '【L5 輔助】未被排除的總任務數 (完成率分母)',
    },

    l5TodoTaskCount: {
      sql: `task_id`,
      type: `count`,
      filters: [
        { sql: `${CUBE}.task_status = 'TODO'` },
        { sql: `${CUBE}.is_excluded = 0` }
      ],
      title: '� L5 待辦任務數',
      description: '【L5 輔助】狀態為 TODO 且未被排除的任務數',
    },

    l5DoingTaskCount: {
      sql: `task_id`,
      type: `count`,
      filters: [
        { sql: `${CUBE}.task_status = 'DOING'` },
        { sql: `${CUBE}.is_excluded = 0` }
      ],
      title: '🥈 L5 進行中任務數',
      description: '【L5 輔助】狀態為 DOING 且未被排除的任務數',
    },

    l5DoneTaskCount: {
      sql: `task_id`,
      type: `count`,
      filters: [
        { sql: `${CUBE}.task_status = 'DONE'` },
        { sql: `${CUBE}.is_excluded = 0` }
      ],
      title: '🥈 L5 已完成任務數',
      description: '【L5 輔助】狀態為 DONE 且未被排除的任務數 (完成率分子)',
    },

    // ==========================================
    // 🔍 除錯與分析指標
    // ==========================================

    excludedTaskCount: {
      sql: `task_id`,
      type: `count`,
      filters: [{ sql: `${CUBE}.is_excluded = 1` }],
      title: '🔍 排除任務數',
      description: '【除錯用】被排除的任務數 (bypass、測試工單等)',
    },

    bypassTaskCount: {
      sql: `task_id`,
      type: `count`,
      filters: [{ sql: `${CUBE}.task_bypass = 'Y'` }],
      title: '🔍 略過任務數',
      description: '【除錯用】被標記為略過的任務數',
    },

    // ==========================================
    // 📊 Vx 分析指標
    // ==========================================

    v1TaskCount: {
      sql: `task_id`,
      type: `count`,
      filters: [
        { sql: `${CUBE}.vx_type = 'V1'` },
        { sql: `${CUBE}.is_excluded = 0` }
      ],
      title: '📊 V1 任務數',
      description: 'Vx 類型為 V1 且未被排除的任務數',
    },

    v2TaskCount: {
      sql: `task_id`,
      type: `count`,
      filters: [
        { sql: `${CUBE}.vx_type = 'V2'` },
        { sql: `${CUBE}.is_excluded = 0` }
      ],
      title: '📊 V2 任務數',
      description: 'Vx 類型為 V2 且未被排除的任務數',
    },

    v3TaskCount: {
      sql: `task_id`,
      type: `count`,
      filters: [
        { sql: `${CUBE}.vx_type = 'V3'` },
        { sql: `${CUBE}.is_excluded = 0` }
      ],
      title: '📊 V3 任務數',
      description: 'Vx 類型為 V3 且未被排除的任務數',
    },
  },
});
