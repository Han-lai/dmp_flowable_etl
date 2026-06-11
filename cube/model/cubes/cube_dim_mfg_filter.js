/**
 * Dashboard 萬用篩選資料集
 * 目的：專為 Superset Native Filter 設計的「輕量化選單模型」。
 * 來源：任務指標 + 人員指標的維度 UNION，確保每個組合在至少一個指標中有真實資料。
 * 動機：MDM 涵蓋範圍遠超系統實際廠區（含 DET/TW/SK 等無任務廠區），以指標 UNION 為準才能過濾雜訊。
 * 擴充：未來新增指標時，在 UNION DISTINCT 區塊補上對應的 SELECT 即可。
 */

cube(`DimMfgFilter`, {
    sql: `
    SELECT DISTINCT vx_type AS vx, region, plant, factory, line
    FROM gold.rmv_l5_task_summary FINAL
    WHERE vx_type IN ('V1', 'V2', 'V3')
      AND region != '' AND plant != '' AND factory != ''

    UNION DISTINCT

    SELECT DISTINCT vx, region, plant, factory, line
    FROM gold.rmv_staff_using_metrics
    WHERE vx IN ('V1', 'V2', 'V3')
      AND region != '' AND plant != '' AND factory != ''
    `,

    title: 'Dashboard 萬用篩選器 (組織五階 + Vx)',
    description: '任務與人員指標維度的聯集，只顯示真實有資料的組合。新增指標在 UNION 區塊補上即可。',

    dimensions: {
        id: {
            sql: `concat(vx, '_', region, '_', plant, '_', factory, '_', line)`,
            type: `string`,
            primaryKey: true
        },

        diffVx:      { type: `string`, sql: `vx`,      title: 'Vx 類型' },
        diffRegion:  { type: `string`, sql: `region`,  title: '地區' },
        diffPlant:   { type: `string`, sql: `plant`,   title: '廠區' },
        diffFactory: { type: `string`, sql: `factory`, title: '工廠' },
        diffLine:    { type: `string`, sql: `line`,    title: '線體' }
    }
});
