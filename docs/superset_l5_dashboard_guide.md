# Superset L5 任務儀表板欄位拉取指南

## 📊 資料源配置

### Cube.js 連接設置
- **資料源名稱**: `L5DashboardSummary`
- **Cube.js API 端點**: `http://your-cubejs-server:4000/cubejs-api/v1`
- **資料庫類型**: Cube.js

### 直接 ClickHouse 連接（備選）
- **資料源**: `gold.vw_superset_l5_summary`
- **連接字串**: `clickhouse://default:default@10.136.218.207:8121/gold`

---

## 🎯 Superset 欄位拉取配置

### 📅 時間維度欄位

| Superset 欄位名稱 | Cube.js 欄位 | 資料類型 | 說明 |
|------------------|-------------|----------|------|
| **快照日期** | `snapshotDate` | Date | 主要時間軸，用於趨勢分析 |
| **年份** | `snapshotYear` | Number | 年度分析 |
| **月份** | `snapshotMonth` | Number | 月度分析 |
| **週次** | `snapshotWeek` | Number | 週度分析 |

### 🏭 主鍵維度欄位

| Superset 欄位名稱 | Cube.js 欄位 | 資料類型 | 說明 |
|------------------|-------------|----------|------|
| **地區** | `region` | String | 地區代碼（製造五階） |
| **廠別** | `plant` | String | 廠別代碼 |
| **工廠** | `factory` | String | 工廠代碼 |
| **線體** | `line` | String | 線體代碼 |
| **Vx類型** | `vxType` | String | V1/V2/V3 分類 |

### 🏷️ 維度名稱欄位（用於顯示）

| Superset 欄位名稱 | Cube.js 欄位 | 資料類型 | 說明 |
|------------------|-------------|----------|------|
| **地區名稱** | `regionName` | String | 地區完整名稱 |
| **廠別名稱** | `plantName` | String | 廠別完整名稱 |
| **工廠名稱** | `factoryName` | String | 工廠完整名稱 |
| **線體名稱** | `lineName` | String | 線體完整名稱 |

### 🔗 組合維度欄位

| Superset 欄位名稱 | Cube.js 欄位 | 資料類型 | 說明 |
|------------------|-------------|----------|------|
| **地區-廠別** | `regionPlant` | String | 地區和廠別組合 |
| **廠別-工廠** | `plantFactory` | String | 廠別和工廠組合 |
| **工廠-線體** | `factoryLine` | String | 工廠和線體組合 |
| **Vx-廠別** | `vxPlant` | String | Vx類型和廠別組合 |
| **維度路徑** | `dimensionPath` | String | 完整路徑 (Region>Plant>Factory>Line) |

---

## 📊 指標欄位配置

### 🔢 任務狀態彙總欄位

| Superset 指標名稱 | Cube.js 欄位 | 聚合方式 | 說明 |
|------------------|-------------|----------|------|
| **任務總數** | `totalTask` | SUM | total_task |
| **Todo數量** | `todoCnt` | SUM | todo_cnt |
| **Doing數量** | `doingCnt` | SUM | doing_cnt |
| **Done數量** | `doneCnt` | SUM | done_cnt |
| **Doing+Done數量** | `doingDoneCnt` | SUM | doing_done_cnt |
| **Todo+Doing數量** | `todoDoingAccCnt` | SUM | todo_doing_acc_cnt |

### 📈 比例欄位（計算指標）

| Superset 指標名稱 | Cube.js 欄位 | 聚合方式 | 計算公式 |
|------------------|-------------|----------|----------|
| **Todo比例** | `todoRate` | AVG | todo_cnt / total_task × 100% |
| **Doing比例** | `doingRate` | AVG | doing_cnt / total_task × 100% |
| **Done比例** | `doneRate` | AVG | done_cnt / total_task × 100% |
| **Doing+Done比例** | `doingDoneRate` | AVG | (doing_cnt + done_cnt) / total_task × 100% |
| **Todo+Doing比例** | `todoDoingAccRate` | AVG | (todo_cnt + doing_cnt) / total_task × 100% |

### 📊 預計算比例欄位（推薦使用）

| Superset 指標名稱 | Cube.js 欄位 | 聚合方式 | 說明 |
|------------------|-------------|----------|------|
| **Todo比例(預計算)** | `preCalculatedTodoRate` | AVG | 視圖預計算，效能更佳 |
| **Doing比例(預計算)** | `preCalculatedDoingRate` | AVG | 視圖預計算，效能更佳 |
| **Done比例(預計算)** | `preCalculatedDoneRate` | AVG | 視圖預計算，效能更佳 |
| **Doing+Done比例(預計算)** | `preCalculatedDoingDoneRate` | AVG | 視圖預計算，效能更佳 |
| **Todo+Doing比例(預計算)** | `preCalculatedTodoDoingAccRate` | AVG | 視圖預計算，效能更佳 |

---

## 🎨 建議的圖表配置

### 📊 圖表 1: L5 任務完成率趨勢圖

**圖表類型**: 線圖 (Line Chart)

**配置**:
- **X軸**: `snapshotDate` (快照日期)
- **Y軸**: `preCalculatedDoneRate` (Done比例-預計算)
- **分組**: `vxType` (Vx類型)
- **篩選器**: 
  - `region` (地區)
  - `plant` (廠別)
  - `snapshotDate` (日期範圍)

**SQL 查詢示例**:
```sql
SELECT 
    snapshot_date,
    vx_type,
    AVG(done_rate) as avg_done_rate
FROM gold.vw_superset_l5_summary
WHERE snapshot_date >= '2026-01-01'
GROUP BY snapshot_date, vx_type
ORDER BY snapshot_date, vx_type
```

### 📊 圖表 2: 任務狀態分佈堆疊柱狀圖

**圖表類型**: 堆疊柱狀圖 (Stacked Bar Chart)

**配置**:
- **X軸**: `plantFactory` (廠別-工廠)
- **Y軸**: 
  - `todoCnt` (Todo數量)
  - `doingCnt` (Doing數量)
  - `doneCnt` (Done數量)
- **篩選器**:
  - `vxType` (Vx類型)
  - `snapshotDate` (最新日期)

### 📊 圖表 3: 維度績效分析表

**圖表類型**: 表格 (Table)

**配置**:
- **行維度**:
  - `regionName` (地區名稱)
  - `plantName` (廠別名稱)
  - `factoryName` (工廠名稱)
  - `lineName` (線體名稱)
- **指標列**:
  - `totalTask` (任務總數)
  - `preCalculatedDoneRate` (完成率)
  - `preCalculatedDoingDoneRate` (執行率)
- **篩選器**:
  - `vxType` (Vx類型)
  - `snapshotDate` (日期)

### 📊 圖表 4: Vx 類型對比雷達圖

**圖表類型**: 雷達圖 (Radar Chart)

**配置**:
- **維度**: `vxType` (V1, V2, V3)
- **指標**:
  - `preCalculatedTodoRate` (Todo比例)
  - `preCalculatedDoingRate` (Doing比例)
  - `preCalculatedDoneRate` (Done比例)

---

## 🎛️ 篩選器配置建議

### 📅 時間篩選器
```javascript
{
  "column": "snapshotDate",
  "type": "time_range",
  "default": "Last 30 days"
}
```

### 🏭 維度篩選器
```javascript
// 地區篩選器
{
  "column": "region",
  "type": "filter_select",
  "multiple": true
}

// Vx類型篩選器
{
  "column": "vxType", 
  "type": "filter_select",
  "multiple": true,
  "default": ["V1", "V2", "V3"]
}

// 廠別篩選器
{
  "column": "plant",
  "type": "filter_select", 
  "multiple": true
}
```

### 📊 績效篩選器
```javascript
// 績效等級篩選器
{
  "column": "performanceLevel",
  "type": "filter_select",
  "multiple": true
}

// 任務量等級篩選器
{
  "column": "volumeLevel",
  "type": "filter_select",
  "multiple": true
}
```

---

## 🚀 效能優化建議

### 1. **使用預計算欄位**
- 優先使用 `preCalculated*` 系列欄位
- 避免在 Superset 中重複計算比例

### 2. **合理設置時間範圍**
- 預設顯示最近 30 天
- 避免查詢過長時間範圍

### 3. **利用預聚合**
- Cube.js 已配置預聚合，查詢會自動優化
- 常用維度組合會被預先計算

### 4. **快取設置**
- 設置合理的快取時間（建議 1 小時）
- 利用 Superset 的查詢快取功能

---

## 📋 完整的儀表板配置範例

### Dashboard JSON 配置
```json
{
  "dashboard_title": "L5 任務執行完成率儀表板",
  "charts": [
    {
      "chart_type": "line",
      "datasource": "L5DashboardSummary",
      "metrics": ["preCalculatedDoneRate"],
      "groupby": ["vxType"],
      "time_range": "Last 30 days",
      "x_axis": "snapshotDate"
    },
    {
      "chart_type": "stacked_bar",
      "datasource": "L5DashboardSummary", 
      "metrics": ["todoCnt", "doingCnt", "doneCnt"],
      "groupby": ["plantFactory"],
      "filters": [
        {"column": "vxType", "value": ["V1"]}
      ]
    }
  ],
  "filters": [
    {"column": "snapshotDate", "type": "time_range"},
    {"column": "vxType", "type": "filter_select"},
    {"column": "region", "type": "filter_select"},
    {"column": "plant", "type": "filter_select"}
  ]
}
```

---

## ⚠️ 注意事項

### 1. **資料更新頻率**
- 彙總表每日更新
- Cube.js 預聚合每小時刷新
- 建議設置自動刷新間隔為 1 小時

### 2. **維度層級**
- 支援從地區到線體的完整五階維度
- 可以進行上鑽下鑽分析
- 注意維度組合的資料量

### 3. **比例計算**
- 建議使用預計算欄位提升效能
- 跨維度聚合時需重新計算比例
- 避免直接平均比例欄位

### 4. **篩選邏輯**
- 支援多選篩選
- 維度篩選會影響所有圖表
- 注意篩選條件的組合邏輯

這個配置可以滿足您的 L5 任務儀表板需求，提供完整的任務狀態分析和趨勢監控功能。