/**
 * Historical Trends View
 * 歷史趨勢查詢介面
 * 
 * 用途:
 * - 對外暴露簡化的歷史趨勢 API
 * - 組合 DailyMetricsSnapshot 和 DailyBizEventSnapshot
 * - 隱藏內部 Cube 複雜度
 * 
 * 查詢範例:
 * {
 *   "measures": ["HistoricalTrends.inProgressTaskCount"],
 *   "timeDimensions": [{
 *     "dimension": "HistoricalTrends.snapshotDate",
 *     "granularity": "day",
 *     "dateRange": "last 30 days"
 *   }]
 * }
 */

view(`HistoricalTrends`, {
  title: '歷史趨勢',
  description: '查詢歷史指標趨勢。支援每日/每週/每月粒度。',

  cubes: [
    {
      join_path: DailyMetricsSnapshot,
      includes: [
        // 時間維度
        { name: 'snapshotDate', alias: 'snapshotDate' },
        
        // 業務維度
        { name: 'factory', alias: 'factory' },
        { name: 'plant', alias: 'plant' },
        { name: 'procDefName', alias: 'procDefName' },
        
        // 🥇 Gold 指標 - 任務
        { name: 'inProgressTaskCount', alias: 'inProgressTaskCount' },
        { name: 'todoCount', alias: 'todoCount' },
        { name: 'doingCount', alias: 'doingCount' },
        
        // 🥇 Gold 指標 - 自動完成率
        { name: 'doneAutoCount', alias: 'doneAutoCount' },
        { name: 'doneTotalCount', alias: 'doneTotalCount' },
        { name: 'autoCompleteRate', alias: 'autoCompleteRate' },
        
        // 🥇 Gold 指標 - 平均處理時長
        { name: 'totalWorkDurationSec', alias: 'totalWorkDurationSec' },
        { name: 'doneCount', alias: 'doneCount' },
        { name: 'avgWorkDurationSec', alias: 'avgWorkDurationSec' },
        { name: 'avgWorkDurationMin', alias: 'avgWorkDurationMin' },
        
        // 🥇 Gold 指標 - 流程
        { name: 'inProgressProcCount', alias: 'inProgressProcCount' },
        { name: 'completedProcCount', alias: 'completedProcCount' },
      ],
    },
  ],
});


view(`HistoricalBizEvents`, {
  title: '歷史業務事件趨勢',
  description: '查詢業務事件歷史趨勢。⚠️ 此 View 沒有廠區維度。',

  cubes: [
    {
      join_path: DailyBizEventSnapshot,
      includes: [
        // 時間維度
        { name: 'snapshotDate', alias: 'snapshotDate' },
        
        // 業務維度
        { name: 'firstProcDefName', alias: 'firstProcDefName' },
        
        // 🥇 Gold 指標 - 業務事件
        { name: 'inProgressEventCount', alias: 'inProgressEventCount' },
        { name: 'completedEventCount', alias: 'completedEventCount' },
        { name: 'totalEventDurationSec', alias: 'totalEventDurationSec' },
        { name: 'avgEventDurationSec', alias: 'avgEventDurationSec' },
        { name: 'avgEventDurationHour', alias: 'avgEventDurationHour' },
      ],
    },
  ],
});
