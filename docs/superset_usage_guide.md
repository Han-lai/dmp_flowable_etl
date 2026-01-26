# Superset L5 Dashboard 使用指南

## 🎯 正確的欄位選擇與聚合方式

### 📊 上方圖表區域

#### 長條圖 - Todo/Doing/Done 分布

**圖表設定**：
- **圖表類型**：Bar Chart (Stacked)
- **X 軸**：`snapshotDate` (時間維度)
- **Y 軸 Metrics**：
  ```
  ✅ totalTask → 聚合選擇：SUM
  ✅ todoTask → 聚合選擇：SUM  
  ✅ doingTask → 聚合選擇：SUM
  ✅ doneTask → 聚合選擇：SUM
  ```
- **分組維度**：`vxScope` (V1/V2/V3)
- **篩選器**：`region`, `plant`, `factory`

#### 折線圖 - 完成率趨勢

**圖表設定**：
- **圖表類型**：Line Chart
- **X 軸**：`snapshotDate` (時間維度)
- **Y 軸 Metrics**：
  ```
  ✅ completionRate → 聚合選擇：AVG (Cube.js 已計算正確比例)
  ✅ progressRate → 聚合選擇：AVG
  ✅ accumulationRate → 聚合選擇：AVG
  ```
- **分組維度**：`vxScope`
- **篩選器**：`region`, `plant`

---

### 📋 下方明細表區域

#### 明細表 - 任務狀態 × 維度

**圖表設定**：
- **圖表類型**：Table
- **分組維度 (Rows)**：
  ```
  ✅ flowTeam (流程團隊)
  ✅ region (地區)  
  ✅ plant (製造廠區)
  ✅ factory (製造產品廠)
  ✅ line (線體)
  ✅ vxScope (任務類型範圍)
  ```

- **數量指標 (Metrics)**：
  ```
  ✅ totalTask → 聚合：SUM → 顯示名稱：任務總數
  ✅ todoTask → 聚合：SUM → 顯示名稱：Todo 任務數
  ✅ doingTask → 聚合：SUM → 顯示名稱：Doing 任務數
  ✅ doneTask → 聚合：SUM → 顯示名稱：Done 任務數
  ✅ doingDoneTask → 聚合：SUM → 顯示名稱：Doing+Done 任務數
  ```

- **比例指標 (Metrics)**：
  ```
  ✅ todoRate → 聚合：AVG → 顯示名稱：Todo 比例 (%)
  ✅ doingRate → 聚合：AVG → 顯示名稱：Doing 比例 (%)
  ✅ doneRate → 聚合：AVG → 顯示名稱：Done 比例 (%)
  ✅ doingDoneRate → 聚合：AVG → 顯示名稱：Doing+Done 比例 (%)
  ```

---

### 🔧 KPI 卡片區域

#### 整體指標卡片

**完成率卡片**：
- **圖表類型**：Big Number
- **Metric**：`completionRate` → 聚合：`AVG`
- **格式**：百分比
- **標題**：整體完成率

**執行率卡片**：
- **圖表類型**：Big Number  
- **Metric**：`progressRate` → 聚合：`AVG`
- **格式**：百分比
- **標題**：整體執行率

**任務總數卡片**：
- **圖表類型**：Big Number
- **Metric**：`totalTask` → 聚合：`SUM`
- **格式**：數字
- **標題**：任務總數

---

## 🚨 重要：聚合函數選擇規則

### ✅ 數量指標 → 永遠選擇 SUM

| Cube Measure | Superset 聚合 | 原因 |
|--------------|---------------|------|
| `totalTask` | **SUM** | 任務數量可以加總 |
| `todoTask` | **SUM** | 任務數量可以加總 |
| `doingTask` | **SUM** | 任務數量可以加總 |
| `doneTask` | **SUM** | 任務數量可以加總 |
| `doingDoneTask` | **SUM** | 組合任務數量可以加總 |
| `todoDoingAccTask` | **SUM** | 組合任務數量可以加總 |

### ✅ 比例指標 → 選擇 AVG

| Cube Measure | Superset 聚合 | 原因 |
|--------------|---------------|------|
| `todoRate` | **AVG** | Cube.js 已正確計算比例 |
| `doingRate` | **AVG** | Cube.js 已正確計算比例 |
| `doneRate` | **AVG** | Cube.js 已正確計算比例 |
| `completionRate` | **AVG** | Cube.js 已正確計算比例 |
| `progressRate` | **AVG** | Cube.js 已正確計算比例 |
| `accumulationRate` | **AVG** | Cube.js 已正確計算比例 |

### ❌ 絕對不要選擇的聚合

| 錯誤選擇 | 為什麼錯誤 | 結果 |
|----------|------------|------|
| `SUM(completionRate)` | 把百分比相加 | 75% + 80% + 65% = 220% ❌ |
| `MAX(totalTask)` | 只取最大值 | 遺失其他資料 ❌ |
| `COUNT(doneTask)` | 計算列數而非任務數 | 完全錯誤 ❌ |

---

## 🔧 Dashboard 篩選器設定

### 全域篩選器

**時間篩選器**：
- **欄位**：`snapshotDate`
- **類型**：Date Range Filter
- **預設範圍**：最近 30 天
- **影響**：所有圖表

**地區篩選器**：
- **欄位**：`region`
- **類型**：Filter Select
- **多選**：是
- **預設**：全選
- **影響**：所有圖表

**廠區篩選器**：
- **欄位**：`plant`
- **類型**：Filter Select
- **多選**：是
- **階層依賴**：region
- **影響**：所有圖表

**工廠篩選器**：
- **欄位**：`factory`
- **類型**：Filter Select
- **多選**：是
- **階層依賴**：plant
- **影響**：所有圖表

**任務類型篩選器**：
- **欄位**：`vxScope`
- **類型**：Filter Select
- **多選**：是
- **選項**：V1, V2, V3, V1+V2+V3
- **影響**：所有圖表

---

## 📊 圖表配置範例

### 長條圖配置 JSON

```json
{
  "viz_type": "dist_bar",
  "datasource": "L5DashboardCompletion",
  "granularity_sqla": "snapshotDate",
  "time_range": "Last 30 days",
  "metrics": [
    {
      "aggregate": "SUM",
      "column": "todoTask",
      "label": "Todo 任務"
    },
    {
      "aggregate": "SUM", 
      "column": "doingTask",
      "label": "Doing 任務"
    },
    {
      "aggregate": "SUM",
      "column": "doneTask", 
      "label": "Done 任務"
    }
  ],
  "groupby": ["vxScope"],
  "adhoc_filters": [
    {
      "clause": "WHERE",
      "subject": "region",
      "operator": "IN",
      "comparator": ["CNE", "CNC"]
    }
  ]
}
```

### 折線圖配置 JSON

```json
{
  "viz_type": "line",
  "datasource": "L5DashboardCompletion", 
  "granularity_sqla": "snapshotDate",
  "time_range": "Last 30 days",
  "metrics": [
    {
      "aggregate": "AVG",
      "column": "completionRate",
      "label": "完成率 (%)"
    },
    {
      "aggregate": "AVG",
      "column": "progressRate", 
      "label": "執行率 (%)"
    }
  ],
  "groupby": ["vxScope"]
}
```

### 明細表配置 JSON

```json
{
  "viz_type": "table",
  "datasource": "L5DashboardCompletion",
  "granularity_sqla": "snapshotDate", 
  "time_range": "Last 7 days",
  "groupby": [
    "flowTeam",
    "region", 
    "plant",
    "factory",
    "line",
    "vxScope"
  ],
  "metrics": [
    {
      "aggregate": "SUM",
      "column": "totalTask",
      "label": "任務總數"
    },
    {
      "aggregate": "SUM",
      "column": "doneTask",
      "label": "完成任務"
    },
    {
      "aggregate": "AVG", 
      "column": "completionRate",
      "label": "完成率 (%)"
    }
  ],
  "percent_metrics": [
    {
      "aggregate": "AVG",
      "column": "completionRate"
    }
  ]
}
```

---

## 🎨 視覺化設定建議

### 顏色配置

**任務狀態顏色**：
```
Todo: #FFA500 (橙色)
Doing: #1E90FF (藍色)
Done: #32CD32 (綠色)
```

**Vx 類型顏色**：
```
V1: #FF6B6B (紅色系)
V2: #4ECDC4 (青色系)  
V3: #45B7D1 (藍色系)
```

### 數值格式

**數量欄位**：
- 格式：`,d` (千分位逗號)
- 範例：1,234

**百分比欄位**：
- 格式：`.1%` (一位小數)
- 範例：75.5%

---

## ⚠️ 常見錯誤與避免方式

### ❌ 錯誤 1：比例指標選擇 SUM

**錯誤操作**：
```
completionRate → 聚合選擇：SUM
結果：75% + 80% + 65% = 220% (無意義)
```

**正確操作**：
```
completionRate → 聚合選擇：AVG
結果：Cube.js 已正確計算的比例
```

### ❌ 錯誤 2：數量指標選擇 AVG

**錯誤操作**：
```
totalTask → 聚合選擇：AVG
結果：(100 + 200 + 150) / 3 = 150 (不是總數)
```

**正確操作**：
```
totalTask → 聚合選擇：SUM  
結果：100 + 200 + 150 = 450 (正確總數)
```

### ❌ 錯誤 3：時間聚合不一致

**錯誤操作**：
```
日資料 → 週資料：直接 AVG(completion_rate)
結果：不考慮任務數量權重的平均
```

**正確操作**：
```
讓 Cube.js 處理時間聚合
Cube.js 會正確計算：SUM(done) / SUM(total) * 100
```

---

## 🎯 快速檢查清單

建立圖表前，請確認：

- [ ] **數量指標都選擇 SUM**
- [ ] **比例指標都選擇 AVG**  
- [ ] **時間維度使用 snapshotDate**
- [ ] **篩選器設定正確的階層關係**
- [ ] **顏色配置符合業務語意**
- [ ] **數值格式設定正確**
- [ ] **圖表標題清楚描述內容**

完成後測試：
- [ ] **數量加總是否合理**
- [ ] **比例是否在 0-100% 範圍內**
- [ ] **篩選器是否正常運作**
- [ ] **時間範圍切換是否正確**