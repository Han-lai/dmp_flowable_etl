/**
 * Dashboard 萬用篩選資料集 (含時間維度)
 * 優化: 加入 ORDER BY 確保最新的日期優先出現在選單中，避免因為組合過多元件導致日期被截斷。
 */

cube(`DimMfgFilter`, {
    sql: `
    SELECT DISTINCT region, plant, factory, line, vx_type, snapshot_date 
    FROM gold.rmv_l5_task_completion
    ORDER BY snapshot_date DESC
    `,
    
    title: 'Dashboard 萬用篩選器 (地區/廠區/時間)',
    description: '提供 Superset 極速下拉選單，並優化日期排序',

    dimensions: {
        id: { 
            sql: `concat(region, '_', plant, '_', factory, '_', line, '_', vx_type, '_', toString(snapshot_date))`, 
            type: `string`, 
            primaryKey: true 
        },
        
        snapshotDate: { 
            type: `string`, 
            sql: `formatDateTime(snapshot_date, '%Y-%m-%d')`, 
            title: '日期篩選' 
        },
        
        diffRegion: { type: `string`, sql: `region`, title: '地區' },
        diffPlant: { type: `string`, sql: `plant`, title: '廠區' },
        diffFactory: { type: `string`, sql: `factory`, title: '工廠' },
        diffLine: { type: `string`, sql: `line`, title: '線體' },
        diffVxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' }
    }
});
