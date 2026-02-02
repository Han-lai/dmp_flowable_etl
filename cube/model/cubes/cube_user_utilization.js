/**
 * 人員使用率 Cube - 新增
 * 
 * 來源表: gold.rmv_user_utilization (新的 REFRESHABLE MView)
 * 用途: 為人員使用率報表提供資料模型
 * 
 * 建立日期: 2026-01-30
 * - 新建 Cube 對應 gold.rmv_user_utilization 表
 * - 表格每小時自動刷新 (REFRESH EVERY 1 HOUR)
 */

cube(`UserUtilization`, {
    sql: `SELECT * FROM gold.rmv_user_utilization FINAL`,

    title: '人員使用率',
    description: '人員任務分配和完成情況分析',

    measures: {
        // ============================================================
        // 人員統計
        // ============================================================
        activeUsers: {
            type: `sum`,
            sql: `active_users`,
            title: '活躍人員數',
            description: '有任務分配的人員數',
        },

        workingUsers: {
            type: `sum`,
            sql: `working_users`,
            title: '工作中人員數',
            description: '有 Todo/Doing 任務的人員數',
        },

        completedUsers: {
            type: `sum`,
            sql: `completed_users`,
            title: '已完成人員數',
            description: '有 Done 任務的人員數',
        },

        // ============================================================
        // 任務統計
        // ============================================================
        totalTasks: {
            type: `sum`,
            sql: `total_tasks`,
            title: '任務總數',
        },

        doneTasks: {
            type: `sum`,
            sql: `done_tasks`,
            title: '已完成任務數',
        },

        // ============================================================
        // 比例指標
        // ============================================================
        utilizationRate: {
            type: `avg`,
            sql: `utilization_rate`,
            title: '使用率 (%)',
            description: 'working_users / active_users × 100%',
            format: `percent`,
        },

        // 每人平均任務數
        tasksPerUser: {
            type: `number`,
            sql: `CASE WHEN ${activeUsers} > 0 THEN ${totalTasks} * 1.0 / ${activeUsers} ELSE 0 END`,
            title: '每人平均任務數',
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
        },

        // ============================================================
        // 維度
        // ============================================================
        vxType: {
            type: `string`,
            sql: `vx_type`,
            title: 'Vx 類型',
            description: 'V1 / V2 / V3',
        },

        plant: {
            type: `string`,
            sql: `COALESCE(NULLIF(plant, ''), 'UNKNOWN')`,
            title: '廠區',
        },

        // ============================================================
        // Metadata
        // ============================================================
        refreshTime: {
            type: `time`,
            sql: `_refresh_time`,
            title: '刷新時間',
        },
    },

    preAggregations: {
        dailySummary: {
            measures: [
                UserUtilization.activeUsers,
                UserUtilization.workingUsers,
                UserUtilization.totalTasks,
                UserUtilization.doneTasks,
            ],
            dimensions: [
                UserUtilization.snapshotDate,
                UserUtilization.vxType,
                UserUtilization.plant,
            ],
            timeDimension: UserUtilization.snapshotDate,
            granularity: `day`,
            refreshKey: {
                every: `1 hour`,
            },
        },
    },
});
