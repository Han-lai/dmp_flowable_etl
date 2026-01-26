# Superset L5 Dashboard 欄位對應指南

## 📊 Cube.js 連接設定

**Data Source**: `L5DashboardCompletion` (Cube.js)
**Connection**: 透過 Cube.js API 連接

---

## 🎯 上方圖表區域

### 📊 長條圖 - Todo/Doing/Done 分布

**圖表類型**: Stacked Bar Chart

**X 軸 (時間軸)**:
- `L5DashboardCompletion.snapshotDate` - 快照日期

**Y 軸 (指標)**:
- `L5DashboardCompletion.todoTask` - Todo 任務數
- `L5DashboardCompletion.doingTask` - Doing 任務數  
- `L5DashboardCompletion.doneTask` - Done 任務數

**分組維度**:
- `L5DashboardCompletion.vxScope` - 任務類型範圍 (V1/V2/V3)

**篩選器**:
- `L5DashboardCompletion.region` - 地區篩選
- `L5DashboardCompletion.plant` - 廠區篩選
- `L5DashboardCompletion.factory` - 工廠篩選

### 📈 折線圖 - 完成率趨勢

**圖表類型**: Line Chart

**X 軸 (時間軸)**:
- `L5DashboardCompletion.snapshotDate` - 快照日期

**Y 軸 (指標)**:
- `L5DashboardCompletion.completionRate` - 完成率 (%)
- `L5DashboardCompletion.progressRate` - 執行率 (%)
- `L5DashboardCompletion.accumulationRate` - 累積率 (%)

**分組維度**:
- `L5DashboardCompletion.vxScope` - 任務類型範圍

**篩選器**:
- `L5DashboardCompletion.region` - 地區篩選
- `L5DashboardCompletion.plant` - 廠區篩選

---

## 📋 下方明細表區域

### 📊 明細表 - 任務狀態 × 維度

**圖表類型**: Table

**列維度 (Rows)**:
- `L5DashboardCompletion.flowTeam` - 流程團隊
- `L5DashboardCompletion.region` - 地區
- `L5DashboardCompletion.plant` - 製造廠區
- `L5DashboardCompletion.factory` - 製造產品廠
- `L5DashboardCompletion.line` - 線體
- `L5DashboardCompletion.vxScope` - 任務類型範圍

**指標 (Metrics)**:

**任務數量**:
- `L5DashboardCompletion.totalTask` - 任務總數
- `L5DashboardCompletion.todoTask` - Todo 任務數
- `L5DashboardCompletion.doingTask` - Doing 任務數
- `L5DashboardCompletion.doneTask` - Done 任務數
- `L5DashboardCompletion.doingDoneTask` - Doing+Done 任務數
- `L5DashboardCompletion.todoDoingAccTask` - Todo+Doing 任務數

**百分比**:
- `L5DashboardCompletion.todoRate` - Todo 比例 (%)
- `L5DashboardCompletion.doingRate` - Doing 比例 (%)
- `L5DashboardCompletion.doneRate` - Done 比例 (%)
- `L5DashboardCompletion.doingDoneRate` - Doing+Done 比例 (%)
- `L5DashboardCompletion.todoDoingAccRate` - Todo+Doing 比例 (%)

**篩選器**:
- `L5DashboardCompletion.snapshotDate` - 日期範圍篩選
- `L5DashboardCompletion.region` - 地區篩選
- `L5DashboardCompletion.plant` - 廠區篩選

---

## 🔧 Dashboard 篩選器設定

### 全域篩選器 (影響所有圖表)

**時間篩選**:
- `L5DashboardCompletion.snapshotDate` - 日期範圍選擇器
  - 類型: Date Range Filter
  - 預設: 最近 30 天

**維度篩選**:
- `L5DashboardCompletion.region` - 地區下拉選單
  - 類型: Filter Select
  - 多選: 是
  
- `L5DashboardCompletion.plant` - 廠區下拉選單
  - 類型: Filter Select  
  - 多選: 是
  - 依賴: region (階層篩選)

- `L5DashboardCompletion.factory` - 工廠下拉選單
  - 類型: Filter Select
  - 多選: 是
  - 依賴: plant (階層篩選)

- `L5DashboardCompletion.vxScope` - 任務類型篩選
  - 類型: Filter Select
  - 多選: 是
  - 選項: V1, V2, V3, V1+V2+V3

---

## 📊 進階圖表配置

### 🎯 KPI 卡片

**整體完成率**:
- 指標: `L5DashboardCompletion.completionRate`
- 圖表類型: Big Number
- 格式: 百分比

**整體執行率**:
- 指標: `L5DashboardCompletion.progressRate`
- 圖表類型: Big Number
- 格式: 百分比

**任務總數**:
- 指標: `L5DashboardCompletion.totalTask`
- 圖表類型: Big Number
- 格式: 數字

### 📈 趨勢分析圖表

**維度分析 - 餅圖**:
- 指標: `L5DashboardCompletion.totalTask`
- 分組: `L5DashboardCompletion.vxScope`
- 圖表類型: Pie Chart

**地區比較 - 橫條圖**:
- X 軸: `L5DashboardCompletion.totalTask`
- Y 軸: `L5DashboardCompletion.region`
- 圖表類型: Horizontal Bar Chart

---

## 🔍 組合維度 (進階用途)

### 位置路徑維度
- `L5DashboardCompletion.locationPath` - Region-Plant-Factory 組合
- `L5DashboardCompletion.fullLocationPath` - 包含 Line 的完整路徑

### 篩選組合維度
- `L5DashboardCompletion.regionPlant` - Region|Plant 組合篩選
- `L5DashboardCompletion.plantFactory` - Plant|Factory 組合篩選
- `L5DashboardCompletion.factoryLine` - Factory|Line 組合篩選

---

## 📊 資料品質監控圖表 (可選)

### 維度資料來源分析

**資料來源分布**:
- 指標: 
  - `L5DashboardCompletion.mdmPrimaryTasks` - MDM 主來源
  - `L5DashboardCompletion.flowableFallbackTasks` - Flowable 輔助來源
  - `L5DashboardCompletion.noDimensionTasks` - 無維度資料
  - `L5DashboardCompletion.bypassTasks` - 旁路任務
- 分組: `L5DashboardCompletion.dimensionSource`
- 圖表類型: Stacked Bar Chart

---

## ⚙️ 建議的 Dashboard 佈局

```
┌─────────────────────────────────────────────────────────────┐
│                    全域篩選器區域                              │
│  [日期範圍] [地區] [廠區] [工廠] [任務類型]                      │
├─────────────────────────────────────────────────────────────┤
│  [整體完成率]  [整體執行率]  [任務總數]  [處理中任務]            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Todo/Doing/Done 長條圖]    │    [完成率趨勢折線圖]          │
│                              │                             │
├─────────────────────────────────────────────────────────────┤
│                     明細表                                   │
│  維度 × 任務狀態 × 百分比                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 顏色配置建議

**任務狀態顏色**:
- Todo: `#FFA500` (橙色)
- Doing: `#1E90FF` (藍色)  
- Done: `#32CD32` (綠色)

**Vx 類型顏色**:
- V1: `#FF6B6B` (紅色系)
- V2: `#4ECDC4` (青色系)
- V3: `#45B7D1` (藍色系)

**百分比格式**:
- 小數位數: 1
- 後綴: %
- 範圍: 0-100%