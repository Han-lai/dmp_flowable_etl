# L5 Dashboard Cube Model 更新完成

## ✅ 完成項目

### 🎯 Cube Model 修改
- **檔案**: `cube_gold_l5_task_completion.js`
- **資料來源**: 使用現有的 `gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV`
- **支援功能**: 基於現有表格結構對應 L5 Dashboard 需求

### 📊 維度支援 (基於現有欄位)
- **flowTeam**: 計算維度，基於 vx_type
- **region/plant/factory/line**: 使用現有的 code/name 欄位，智能 fallback
- **vxScope**: 計算維度，基於 vx_type 轉換
- **timeLevel/timeValue**: 固定為 Day 層級 (現有表格限制)

### 📈 指標支援 (基於現有欄位)
- **任務狀態數量**: sum_total_task_qty, sum_todo_qty, sum_doing_qty, sum_done_qty
- **組合狀態**: 動態計算 doingDoneTask, todoDoingAccTask
- **百分比指標**: 動態計算所有狀態的比例
- **預計算指標**: completion_rate, progress_rate (來自現有表格)
- **維度品質**: MDM/Flowable/無維度任務數量統計

### ⚡ 效能優化
- **預聚合配置**: 針對 Dashboard 圖表和明細表優化
- **維度品質監控**: 支援資料來源品質分析
- **查詢效能**: 每小時自動刷新

## 🎯 Dashboard 對應

### 上方圖表
- **長條圖**: Todo/Doing/Done 分布 (基於 sum_*_qty 欄位)
- **折線圖**: 完成率、執行率趨勢 (動態計算)

### 下方明細表
- **維度**: flowTeam, region, plant, factory, line, vxScope (計算維度)
- **指標**: 任務數量 + 百分比 (動態計算)
- **篩選**: 時間、維度組合

## 🔧 現有表格欄位對應

| Dashboard 需求 | 現有欄位 | 處理方式 |
|----------------|----------|----------|
| flow_team | vx_type | 計算維度：基於 vx_type 生成 |
| region | region_code/region_name | 智能 fallback，優先使用 code |
| plant | plant_code/plant_name/plant | 智能 fallback，多層次 fallback |
| factory | factory_code/factory_name/factory | 智能 fallback，多層次 fallback |
| line | line_code/line_name/line | 智能 fallback，可為空 |
| vx_scope | vx_type | 計算維度：V1/V2/V3 或組合 |
| time_level | 固定 'Day' | 現有表格只支援日層級 |
| *_task_qty | sum_*_qty | 直接對應現有欄位 |
| *_task_pct | 動態計算 | 基於數量欄位動態計算百分比 |

## ⚠️ 注意事項

1. **資料來源**: 直接使用現有的 `gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV`
2. **時間層級限制**: 目前只支援 Day 層級，Week/Month 需要額外聚合
3. **Cube 重啟**: 修改後需要重啟 Cube.js 服務
4. **維度計算**: flow_team 和 vx_scope 為計算維度，基於現有 vx_type 欄位

## 🔧 使用方式

```javascript
// Dashboard 圖表查詢範例
{
  "measures": ["L5DashboardCompletion.totalTask", "L5DashboardCompletion.completionRate"],
  "dimensions": ["L5DashboardCompletion.snapshotDate", "L5DashboardCompletion.vxScope"],
  "filters": [
    {"member": "L5DashboardCompletion.region", "operator": "equals", "values": ["CNE"]},
    {"member": "L5DashboardCompletion.plant", "operator": "equals", "values": ["WJ2"]}
  ]
}
```

## 📊 資料品質監控

Cube Model 包含維度資料來源品質監控：
- **mdmPrimaryTasks**: 來自 MDM 主檔的任務數
- **flowableFallbackTasks**: 使用 Flowable 變數的任務數  
- **noDimensionTasks**: 無維度資料的任務數
- **bypassTasks**: 旁路任務數