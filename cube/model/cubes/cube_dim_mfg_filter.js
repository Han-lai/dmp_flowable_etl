/**
 * 製造階層輕量級維度模型 (適用於 Superset Dashboard 篩選器)
 * 
 * 目的: 專門解決 Superset 下拉選單在請求不含 Measure 時，觸發複雜 CTE 導致 60 秒 Timeout 的問題。
 * 此模型在底層 ClickHouse 耗時僅需 0.1 秒，推薦掛載所有 Dashboard 篩選器。
 */

cube(`DimMfgFilter`, {
    sql: `SELECT DISTINCT region, plant, factory, line, vx_type FROM gold.rmv_l5_task_completion`,
    
    title: 'Dashboard 快速篩選器專用',
    description: '提供 Superset 極速下拉選單，避免 Network Error',

    dimensions: {
        id: { sql: `concat(region, '_', plant, '_', factory, '_', line, '_', vx_type)`, type: `string`, primaryKey: true },
        
        region: { type: `string`, sql: `region`, title: '地區' },
        plant: { type: `string`, sql: `plant`, title: '廠區' },
        factory: { type: `string`, sql: `factory`, title: '工廠' },
        line: { type: `string`, sql: `line`, title: '線體' },
        vxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' }
    }
});
