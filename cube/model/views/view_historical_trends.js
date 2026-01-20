/**
 * Historical Trends View - L5 指標專用
 * L5 任務完成率歷史趨勢查詢介面
 * 
 * 用途:
 * - 對外暴露 L5 指標歷史趨勢 API
 * - 基於 DailyMetricsSnapshot (L5 專用表)
 * - 隱藏內部 Cube 複雜度
 */

view(`HistoricalTrends`, {
  title: 'L5 歷史趨勢',
  description: '查詢 L5 任務完成率歷史趨勢。支援每日/每週/每月粒度。',

  cubes: [
    {
      join_path: DailyMetricsSnapshot,
      includes: [
        // 時間維度
        { name: 'snapshotDate', alias: 'snapshotDate' },
        
        // L5 業務維度
        { name: 'vxType', alias: 'vxType' },
        { name: 'vxSubtype', alias: 'vxSubtype' },
        { name: 'plant', alias: 'plant' },
        { name: 'factory', alias: 'factory' },
        { name: 'line', alias: 'line' },
        { name: 'timePeriodType', alias: 'timePeriodType' },
        
        // 🥇 L5 核心指標
        { name: 'l5TotalTaskQty', alias: 'l5TotalTaskQty' },
        { name: 'l5TodoQty', alias: 'l5TodoQty' },
        { name: 'l5DoingQty', alias: 'l5DoingQty' },
        { name: 'l5DoneQty', alias: 'l5DoneQty' },
        { name: 'l5InProgressQty', alias: 'l5InProgressQty' },
        
        // 🥇 L5 完成率指標
        { name: 'l5DonePct', alias: 'l5CompletionRate' },
        { name: 'l5DoingDonePct', alias: 'l5ExecutionRate' },
        { name: 'l5CompletionRate', alias: 'l5CompletionRateCalc' },
        { name: 'l5ExecutionRate', alias: 'l5ExecutionRateCalc' },
      ],
    },
  ],
});
