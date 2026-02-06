/**
 * L5 任務完成率 Cube - 轉置版 (Pivoted for Superset 2026-02-05)
 * 
 * 來源表: gold.rmv_l5_task_completion
 * 用途: 支援 L5 Status Comparison Report，讓指標轉換為維度以固定在縱軸顯示。
 */

cube(`L5TaskCompletion`, {
    sql: `
    SELECT * FROM (
      SELECT 
        snapshot_date, region, plant, factory, line, vx_type, _refresh_time,
        '1. Total Task' as status_name, total_task as task_qty, 100.0 as task_pct, 1 as sort_order
      FROM gold.rmv_l5_task_completion
      UNION ALL
      SELECT 
        snapshot_date, region, plant, factory, line, vx_type, _refresh_time,
        '2. Todo' as status_name, todo_count as task_qty, 
        round(todo_count * 100.0 / nullIf(total_task, 0), 2) as task_pct, 2 as sort_order
      FROM gold.rmv_l5_task_completion
      UNION ALL
      SELECT 
        snapshot_date, region, plant, factory, line, vx_type, _refresh_time,
        '3. Doing' as status_name, doing_count as task_qty, 
        round(doing_count * 100.0 / nullIf(total_task, 0), 2) as task_pct, 3 as sort_order
      FROM gold.rmv_l5_task_completion
      UNION ALL
      SELECT 
        snapshot_date, region, plant, factory, line, vx_type, _refresh_time,
        '4. Done' as status_name, done_count as task_qty, 
        round(done_count * 100.0 / nullIf(total_task, 0), 2) as task_pct, 4 as sort_order
      FROM gold.rmv_l5_task_completion
      UNION ALL
      SELECT 
        snapshot_date, region, plant, factory, line, vx_type, _refresh_time,
        '5. Doing+Done' as status_name, (doing_count + done_count) as task_qty, 
        round((doing_count + done_count) * 100.0 / nullIf(total_task, 0), 2) as task_pct, 5 as sort_order
      FROM gold.rmv_l5_task_completion
      UNION ALL
      SELECT 
        snapshot_date, region, plant, factory, line, vx_type, _refresh_time,
        '6. Todo+Doing(Acc)' as status_name, acc_todo_doing as task_qty, 
        round(acc_todo_doing * 100.0 / nullIf(total_task, 0), 2) as task_pct, 6 as sort_order
      FROM gold.rmv_l5_task_completion
    ) AS pivoted
    `,

    title: 'L5 任務完成率',
    description: 'L5 任務執行指標，指標已轉置為維度以利 Superset 展示',

    measures: {
        taskQty: {
            type: `sum`,
            sql: `task_qty`,
            title: 'Task Qty',
        },
        taskPct: {
            type: `avg`,
            sql: `task_pct`,
            title: 'Task (%)'
        }
    },

    dimensions: {
        id: {
            sql: `concat(toString(snapshot_date), '_', region, '_', plant, '_', factory, '_', line, '_', vx_type, '_', status_name)`,
            type: `string`,
            primaryKey: true,
        },

        snapshotDate: {
            type: `time`,
            sql: `snapshot_date`,
            title: '快照日期',
        },

        statusName: {
            type: `string`,
            sql: `status_name`,
            title: '任務狀態',
        },

        sortOrder: {
            type: `number`,
            sql: `sort_order`,
            title: '排序序號',
        },

        vxType: {
            type: `string`,
            sql: `vx_type`,
            title: 'Vx 類型',
        },

        region: {
            type: `string`,
            sql: `COALESCE(NULLIF(region, ''), 'UNKNOWN')`,
            title: '地區',
        },

        plant: {
            type: `string`,
            sql: `COALESCE(NULLIF(plant, ''), 'UNKNOWN')`,
            title: '廠區',
        },

        factory: {
            type: `string`,
            sql: `COALESCE(NULLIF(factory, ''), 'UNKNOWN')`,
            title: '工廠',
        },

        line: {
            type: `string`,
            sql: `COALESCE(NULLIF(line, ''), '')`,
            title: '線體',
        }
    }
});
