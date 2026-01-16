# Cube.js 指標應用手冊

**版本：** 1.0  
**更新日期：** 2026-01-12  
**適用範圍：** DMP Flowable 流程分析系統

---

## 一、總覽

### 1.1 Cubes 列表

| Cube | 來源表 | 主鍵 | Grain | 用途 |
|------|--------|------|-------|------|
| `ProcTaskNode` | `silver.RMV_HI_PROC_TASK_NODE` | TASK_ID | 一個任務一列 | 任務層級分析 |
| `ProcInstNode` | `silver.RMV_HI_PROCINST_NODE` | PROC_INST_ID | 一個流程一列 | 流程層級分析 |
| `BizEventInfo` | `silver.RMV_HI_BIZ_EVENT_INFO` | BIZ_EVENT_KEY | 一個業務事件一列 | 業務事件層級分析 |

### 1.2 Joins

目前無跨 Cube 的 joins 定義。三個 Cube 獨立運作。

### 1.3 Pre-aggregations / refreshKey

目前停用（ClickHouse 需要指定 indexes，開發階段先不啟用）。

### 1.4 Data Source

- ClickHouse: `REDACTED_IP:8121`
- Database: `silver`
- RMV 刷新頻率: 每天 02:00

---

## 二、Dimensions 總覽

### 2.1 ProcTaskNode (任務節點)

| Dimension | 欄位 | 類型 | 說明 |
|-----------|------|------|------|
| `taskId` | TASK_ID | string | 主鍵 |
| `procInstId` | PROC_INST_ID | string | 流程實例 ID |
| `procDefName` | PROC_DEF_NAME | string | 流程定義名稱 |
| `businessKey` | BUSINESS_KEY | string | 業務事件 Key |
| `taskName` | TASK_NAME | string | 任務名稱 |
| `taskStatus` | TASK_STATUS | string | 任務狀態 (TODO/DOING/DONE/DONE_AUTO/CANCELLED) |
| `assignee` | ASSIGNEE | string | 指派人員 |
| `deptName` | DEPT_NAME | string | 部門名稱 |
| `factory` | FACTORY | string | 工廠 |
| `plant` | PLANT | string | 產品線 |
| `lineName` | LINE_NAME | string | 線別 |
| `region` | REGION | string | 地區 |
| `startTime` | START_TIME | time | 開始時間 |
| `endTime` | END_TIME | time | 結束時間 |
| `claimTime` | CLAIM_TIME | time | 認領時間 |

### 2.2 ProcInstNode (流程實例)

| Dimension | 欄位 | 類型 | 說明 |
|-----------|------|------|------|
| `procInstId` | PROC_INST_ID | string | 主鍵 |
| `procDefName` | PROC_DEF_NAME | string | 流程定義名稱 |
| `businessKey` | BUSINESS_KEY | string | 業務事件 Key |
| `depth` | DEPTH | number | 流程深度 (0=主流程, 1+=子流程) |
| `superId` | SUPER_ID | string | 父流程 ID |
| `factory` | FACTORY | string | 工廠 |
| `plant` | PLANT | string | 產品線 |
| `lineName` | LINE_NAME | string | 線別 |
| `region` | REGION | string | 地區 |
| `procState` | PROC_STATE | string | 流程狀態 |
| `isCompleted` | IS_COMPLETED | number | 是否完成 (0/1) |
| `startTime` | START_TIME | time | 開始時間 |
| `endTime` | END_TIME | time | 結束時間 |

### 2.3 BizEventInfo (業務事件)

| Dimension | 欄位 | 類型 | 說明 |
|-----------|------|------|------|
| `bizEventKey` | BIZ_EVENT_KEY | string | 主鍵 |
| `firstProcDefName` | FIRST_PROC_DEF_NAME | string | 首個流程定義名稱 |
| `firstStartTime` | FIRST_START_TIME | time | 首個任務開始時間 |
| `finalEndTime` | FINAL_END_TIME | time | 最後任務結束時間 |
| `isInProgress` | IS_IN_PROGRESS | number | 是否在途 (0/1) |

⚠️ **注意：BizEventInfo 沒有廠區維度 (factory/plant/lineName)**

---

## 三、Measures 總覽

### 3.1 ProcTaskNode

| Measure | Type | SQL/Filter | 說明 |
|---------|------|------------|------|
| `count` | count | - | 任務總數 |
| `inProgressTaskCount` | count | TASK_STATUS IN ('TODO', 'DOING') | 在途任務數 |
| `todoCount` | count | TASK_STATUS = 'TODO' | TODO 任務數 |
| `doingCount` | count | TASK_STATUS = 'DOING' | DOING 任務數 |
| `doneCount` | count | TASK_STATUS = 'DONE' | DONE 任務數 |
| `doneAutoCount` | count | TASK_STATUS = 'DONE_AUTO' | DONE_AUTO 任務數 |
| `cancelledCount` | count | TASK_STATUS = 'CANCELLED' | CANCELLED 任務數 |
| `autoCompleteRate` | number | doneAutoForRate * 100.0 / NULLIF(doneTotalForRate, 0) | 自動完成率 (%) |
| `avgWorkDuration` | avg | WORK_DURATION_SEC (DONE only) | 平均任務處理時長 (秒) |
| `totalWorkDuration` | sum | WORK_DURATION_SEC (DONE only) | 處理時長總和 (秒) |
| `avgIdleDuration` | avg | IDLE_DURATION_SEC | 平均閒置時長 (秒) |

### 3.2 ProcInstNode

| Measure | Type | SQL/Filter | 說明 |
|---------|------|------------|------|
| `count` | count | - | 流程實例總數 |
| `inProgressCount` | count | IS_COMPLETED = 0 | 在途流程數 |
| `completedCount` | count | IS_COMPLETED = 1 | 已完成流程數 |
| `mainProcCount` | count | DEPTH = 0 | 主流程數 |
| `subProcCount` | count | DEPTH > 0 | 子流程數 |
| `avgDuration` | avg | DURATION_SEC (completed only) | 平均流程時長 (秒) |

### 3.3 BizEventInfo

| Measure | Type | SQL/Filter | 說明 |
|---------|------|------------|------|
| `count` | count | - | 業務事件總數 |
| `inProgressEventCount` | count | IS_IN_PROGRESS = 1 | 在途業務事件數 |
| `completedEventCount` | count | IS_IN_PROGRESS = 0 | 已完成業務事件數 |
| `inProgressTaskCount` | sum | TASK_TODO_CNT + TASK_DOING_CNT (in progress only) | 在途任務數 (從事件) |
| `avgTotalDuration` | avg | TOTAL_DURATION_SEC (completed only) | 平均業務事件總歷時 (秒) |
| `totalDurationSum` | sum | TOTAL_DURATION_SEC (completed only) | 總歷時總和 (秒) |
| `totalTaskCount` | sum | 所有狀態任務數加總 | 任務總數 (從事件) |
| `processCount` | sum | PROCESS_COUNT | 流程數 |

---

## 四、Time Dimensions

| Cube | 時間欄位 | 建議粒度 | 用途 |
|------|----------|----------|------|
| ProcTaskNode | `startTime` | day/week/month | 任務開始時間趨勢 |
| ProcTaskNode | `endTime` | day/week/month | 任務完成時間趨勢 |
| ProcTaskNode | `claimTime` | day/week/month | 任務認領時間趨勢 |
| ProcInstNode | `startTime` | day/week/month | 流程開始時間趨勢 |
| ProcInstNode | `endTime` | day/week/month | 流程完成時間趨勢 |
| BizEventInfo | `firstStartTime` | day/week/month | 業務事件開始趨勢 |
| BizEventInfo | `finalEndTime` | day/week/month | 業務事件完成趨勢 |

---

## 五、指標字典


### 5.1 在途任務數 (`ProcTaskNode.inProgressTaskCount`)

**定義：** 狀態為 TODO 或 DOING 的任務數量，反映系統中待處理的工作量。

**Cube.js 來源：**
- cube: `ProcTaskNode`
- measure type: `count`
- SQL: `COUNT(TASK_ID) WHERE TASK_STATUS IN ('TODO', 'DOING')`

**適用場景：**
- 監控系統整體工作負荷
- 識別哪些廠區/部門/人員任務積壓
- 資源調配決策依據

**建議切法 (Dimensions)：**
- `plant` - 按產品線分析
- `factory` - 按工廠分析
- `deptName` - 按部門分析
- `assignee` - 按人員分析
- `procDefName` - 按流程類型分析
- `taskStatus` - 區分 TODO vs DOING

**建議時間用法：**
- 時間欄位: 不適用（快照指標）
- 粒度: N/A
- 說明: 此為時點指標，顯示當下狀態，不適合做時間序列

**常見圖表：**
- KPI Number (單一數字)
- Bar Chart (按維度比較)
- Table (明細列表)

**常用篩選：**
- `taskStatus = 'TODO'` - 只看待辦
- `taskStatus = 'DOING'` - 只看處理中
- `plant = 'xxx'` - 特定產品線

**例子：**

1) 查詢各廠區在途任務數
```json
{
  "measures": ["ProcTaskNode.inProgressTaskCount"],
  "dimensions": ["ProcTaskNode.plant"],
  "order": { "ProcTaskNode.inProgressTaskCount": "desc" }
}
```

2) Dashboard 視角：部門工作負荷排行
```json
{
  "measures": ["ProcTaskNode.inProgressTaskCount"],
  "dimensions": ["ProcTaskNode.deptName"],
  "order": { "ProcTaskNode.inProgressTaskCount": "desc" },
  "limit": 10
}
```

**注意事項：**
- ⚠️ 快照指標，不可跨時間加總
- ⚠️ 各維度加總應等於總在途任務數
- ⚠️ NULL 值需歸類為 'Unknown'

---

### 5.2 任務狀態分布 (`ProcTaskNode.todoCount` / `doingCount` / `doneCount` / `doneAutoCount` / `cancelledCount`)

**定義：** 所有任務按狀態的數量分布，反映任務生命週期狀態。

**Cube.js 來源：**
- cube: `ProcTaskNode`
- measure type: `count`
- SQL: 各狀態分別 COUNT

**適用場景：**
- 系統健康度檢查
- 識別異常狀態（CANCELLED 過多）
- 自動化程度評估（DONE_AUTO 佔比）

**建議切法 (Dimensions)：**
- `plant` - 按產品線分析
- `factory` - 按工廠分析
- `procDefName` - 按流程類型分析

**建議時間用法：**
- 時間欄位: 不適用（快照指標）
- 粒度: N/A

**常見圖表：**
- Pie Chart (狀態佔比)
- Stacked Bar (按維度的狀態分布)
- Table (各狀態數量)

**常用篩選：**
- 無特定篩選，通常查全量

**例子：**

1) 查詢整體狀態分布
```json
{
  "measures": [
    "ProcTaskNode.todoCount",
    "ProcTaskNode.doingCount",
    "ProcTaskNode.doneCount",
    "ProcTaskNode.doneAutoCount",
    "ProcTaskNode.cancelledCount"
  ]
}
```

2) Dashboard 視角：各廠區狀態分布
```json
{
  "measures": [
    "ProcTaskNode.todoCount",
    "ProcTaskNode.doingCount",
    "ProcTaskNode.doneCount"
  ],
  "dimensions": ["ProcTaskNode.plant"]
}
```

**注意事項：**
- ⚠️ 各狀態數量加總應等於 `count`
- ⚠️ 快照指標，不可跨時間加總

---

### 5.3 自動完成率 (`ProcTaskNode.autoCompleteRate`)

**定義：** DONE_AUTO 任務數 / (DONE + DONE_AUTO) 任務數 × 100%，反映流程自動化程度。

**Cube.js 來源：**
- cube: `ProcTaskNode`
- measure type: `number`
- SQL: `doneAutoForRate * 100.0 / NULLIF(doneTotalForRate, 0)`

**適用場景：**
- 評估流程自動化效率
- 識別可優化的流程
- 自動化推廣成效追蹤

**建議切法 (Dimensions)：**
- `procDefName` - 按流程類型分析（最常用）
- `plant` - 按產品線分析
- `factory` - 按工廠分析

**建議時間用法：**
- 時間欄位: `endTime`
- 粒度: week/month
- 說明: 可追蹤自動化率變化趨勢

**常見圖表：**
- KPI Number (單一數字)
- Bar Chart (按流程比較)
- Time Series (趨勢變化)

**常用篩選：**
- 無特定篩選

**例子：**

1) 查詢各流程自動完成率
```json
{
  "measures": ["ProcTaskNode.autoCompleteRate"],
  "dimensions": ["ProcTaskNode.procDefName"],
  "order": { "ProcTaskNode.autoCompleteRate": "desc" }
}
```

2) Dashboard 視角：自動完成率 Top 10 流程
```json
{
  "measures": [
    "ProcTaskNode.autoCompleteRate",
    "ProcTaskNode.doneAutoCount",
    "ProcTaskNode.doneTotalForRate"
  ],
  "dimensions": ["ProcTaskNode.procDefName"],
  "order": { "ProcTaskNode.autoCompleteRate": "desc" },
  "limit": 10
}
```

**注意事項：**
- ⚠️ 不可將各維度的比率直接平均
- ⚠️ 跨維度聚合需用 `doneAutoForRate` / `doneTotalForRate` 重新計算
- ⚠️ 只計算已完成任務，不含 TODO/DOING/CANCELLED

---

### 5.4 平均任務處理時長 (`ProcTaskNode.avgWorkDuration`)

**定義：** 已完成任務 (DONE) 的處理時長平均值（秒），反映人員處理效率。

**Cube.js 來源：**
- cube: `ProcTaskNode`
- measure type: `avg`
- SQL: `AVG(WORK_DURATION_SEC) WHERE TASK_STATUS = 'DONE'`

**適用場景：**
- 評估人員處理效率
- 識別處理瓶頸
- 流程優化依據

**建議切法 (Dimensions)：**
- `assignee` - 按人員分析
- `procDefName` - 按流程類型分析
- `taskName` - 按任務類型分析
- `plant` - 按產品線分析

**建議時間用法：**
- 時間欄位: `endTime`
- 粒度: week/month
- 說明: 追蹤效率變化趨勢

**常見圖表：**
- Bar Chart (按維度比較)
- Time Series (趨勢變化)
- Table (明細)

**常用篩選：**
- 無特定篩選（已內建 DONE 篩選）

**例子：**

1) 查詢各人員平均處理時長
```json
{
  "measures": ["ProcTaskNode.avgWorkDuration"],
  "dimensions": ["ProcTaskNode.assignee"],
  "order": { "ProcTaskNode.avgWorkDuration": "desc" }
}
```

2) Dashboard 視角：各流程處理效率比較
```json
{
  "measures": [
    "ProcTaskNode.avgWorkDuration",
    "ProcTaskNode.doneCount"
  ],
  "dimensions": ["ProcTaskNode.procDefName"],
  "order": { "ProcTaskNode.avgWorkDuration": "desc" }
}
```

**注意事項：**
- ⚠️ 不可將各維度的平均值直接平均
- ⚠️ 跨維度聚合需用 `totalWorkDuration` / `doneCount` 重新計算
- ⚠️ 只計算 DONE 狀態，不含 DONE_AUTO

---

### 5.5 在途業務事件數 (`BizEventInfo.inProgressEventCount`)

**定義：** 尚未完成的業務事件數量，反映系統中正在處理的業務量。

**Cube.js 來源：**
- cube: `BizEventInfo`
- measure type: `count`
- SQL: `COUNT(BIZ_EVENT_KEY) WHERE IS_IN_PROGRESS = 1`

**適用場景：**
- 監控系統整體業務負荷
- 業務量趨勢分析
- 容量規劃依據

**建議切法 (Dimensions)：**
- `firstProcDefName` - 按流程類型分析
- ⚠️ 此 Cube 沒有廠區維度

**建議時間用法：**
- 時間欄位: 不適用（快照指標）
- 粒度: N/A

**常見圖表：**
- KPI Number (單一數字)
- Bar Chart (按流程比較)

**常用篩選：**
- 無特定篩選

**例子：**

1) 查詢在途業務事件總數
```json
{
  "measures": ["BizEventInfo.inProgressEventCount"]
}
```

2) Dashboard 視角：各流程在途事件數
```json
{
  "measures": ["BizEventInfo.inProgressEventCount"],
  "dimensions": ["BizEventInfo.firstProcDefName"],
  "order": { "BizEventInfo.inProgressEventCount": "desc" },
  "limit": 10
}
```

**注意事項：**
- ⚠️ 快照指標，不可跨時間加總
- ⚠️ 此 Cube 沒有廠區維度 (plant/factory/lineName)
- ⚠️ 如需廠區分析，請用 `ProcTaskNode` 或 `ProcInstNode`

---

### 5.6 平均業務事件總歷時 (`BizEventInfo.avgTotalDuration`)

**定義：** 已完成業務事件的總歷時平均值（秒），反映業務流程整體效率。

**Cube.js 來源：**
- cube: `BizEventInfo`
- measure type: `avg`
- SQL: `AVG(TOTAL_DURATION_SEC) WHERE IS_IN_PROGRESS = 0`

**適用場景：**
- 評估業務流程整體效率
- 識別耗時過長的流程
- 流程優化依據

**建議切法 (Dimensions)：**
- `firstProcDefName` - 按流程類型分析

**建議時間用法：**
- 時間欄位: `finalEndTime`
- 粒度: week/month
- 說明: 追蹤效率變化趨勢

**常見圖表：**
- Bar Chart (按流程比較)
- Time Series (趨勢變化)
- KPI Number (單一數字)

**常用篩選：**
- 無特定篩選（已內建完成篩選）

**例子：**

1) 查詢各流程平均歷時
```json
{
  "measures": ["BizEventInfo.avgTotalDuration"],
  "dimensions": ["BizEventInfo.firstProcDefName"],
  "order": { "BizEventInfo.avgTotalDuration": "desc" }
}
```

2) Dashboard 視角：業務效率概覽
```json
{
  "measures": [
    "BizEventInfo.avgTotalDuration",
    "BizEventInfo.completedEventCount"
  ],
  "dimensions": ["BizEventInfo.firstProcDefName"]
}
```

**注意事項：**
- ⚠️ 不可將各維度的平均值直接平均
- ⚠️ 跨維度聚合需用 `totalDurationSum` / `completedEventCount` 重新計算
- ⚠️ 只計算已完成事件

---

### 5.7 在途流程數 (`ProcInstNode.inProgressCount`)

**定義：** 尚未完成的流程實例數量。

**Cube.js 來源：**
- cube: `ProcInstNode`
- measure type: `count`
- SQL: `COUNT(PROC_INST_ID) WHERE IS_COMPLETED = 0`

**適用場景：**
- 監控流程執行狀態
- 識別卡住的流程
- 流程健康度檢查

**建議切法 (Dimensions)：**
- `procDefName` - 按流程類型分析
- `plant` - 按產品線分析
- `factory` - 按工廠分析
- `depth` - 區分主流程/子流程

**建議時間用法：**
- 時間欄位: 不適用（快照指標）
- 粒度: N/A

**常見圖表：**
- KPI Number
- Bar Chart
- Table

**常用篩選：**
- `depth = 0` - 只看主流程
- `depth > 0` - 只看子流程

**例子：**

1) 查詢各流程在途數
```json
{
  "measures": ["ProcInstNode.inProgressCount"],
  "dimensions": ["ProcInstNode.procDefName"],
  "order": { "ProcInstNode.inProgressCount": "desc" }
}
```

2) Dashboard 視角：主流程 vs 子流程
```json
{
  "measures": [
    "ProcInstNode.mainProcCount",
    "ProcInstNode.subProcCount"
  ],
  "filters": [
    { "member": "ProcInstNode.isCompleted", "operator": "equals", "values": ["0"] }
  ]
}
```

**注意事項：**
- ⚠️ 快照指標，不可跨時間加總
- ⚠️ 一個業務事件可能有多個流程實例（主流程+子流程）

---

### 5.8 平均流程時長 (`ProcInstNode.avgDuration`)

**定義：** 已完成流程實例的時長平均值（秒）。

**Cube.js 來源：**
- cube: `ProcInstNode`
- measure type: `avg`
- SQL: `AVG(DURATION_SEC) WHERE IS_COMPLETED = 1`

**適用場景：**
- 評估流程執行效率
- 識別耗時過長的流程
- 流程優化依據

**建議切法 (Dimensions)：**
- `procDefName` - 按流程類型分析
- `plant` - 按產品線分析
- `depth` - 區分主流程/子流程

**建議時間用法：**
- 時間欄位: `endTime`
- 粒度: week/month

**常見圖表：**
- Bar Chart
- Time Series
- Table

**常用篩選：**
- `depth = 0` - 只看主流程
- `depth > 0` - 只看子流程

**例子：**

1) 查詢各流程平均時長
```json
{
  "measures": ["ProcInstNode.avgDuration"],
  "dimensions": ["ProcInstNode.procDefName"],
  "order": { "ProcInstNode.avgDuration": "desc" }
}
```

**注意事項：**
- ⚠️ 不可將各維度的平均值直接平均
- ⚠️ 只計算已完成流程

---


## 六、維度階層關係

```
FACTORY (工廠)
  └── PLANT (產品線)
        └── LINE_NAME (線別)
```

**可用維度對照：**

| 維度 | ProcTaskNode | ProcInstNode | BizEventInfo |
|------|:------------:|:------------:|:------------:|
| factory | ✅ | ✅ | ❌ |
| plant | ✅ | ✅ | ❌ |
| lineName | ✅ | ✅ | ❌ |
| region | ✅ | ✅ | ❌ |
| deptName | ✅ | ❌ | ❌ |
| assignee | ✅ | ❌ | ❌ |
| procDefName | ✅ | ✅ | ✅ (firstProcDefName) |
| taskStatus | ✅ | ❌ | ❌ |
| depth | ❌ | ✅ | ❌ |

---

## 七、FAQ / 常見錯用

### Q1: 為什麼 BizEventInfo 不能按廠區分析？

**原因：** `RMV_HI_BIZ_EVENT_INFO` 是按 BUSINESS_KEY 聚合的表，沒有保留廠區維度欄位。

**解法：** 如需按廠區分析業務事件，請用 `ProcTaskNode` 或 `ProcInstNode`，透過 `businessKey` 關聯。

---

### Q2: 為什麼跨維度聚合自動完成率結果不對？

**錯誤做法：**
```json
// 錯誤：直接平均各 Plant 的自動完成率
{
  "measures": ["ProcTaskNode.autoCompleteRate"],
  "dimensions": ["ProcTaskNode.factory"]
}
```

**正確做法：** 使用分子分母重新計算
```json
{
  "measures": [
    "ProcTaskNode.doneAutoForRate",
    "ProcTaskNode.doneTotalForRate"
  ],
  "dimensions": ["ProcTaskNode.factory"]
}
// 前端計算: doneAutoForRate / doneTotalForRate * 100
```

---

### Q3: 為什麼同一個指標在不同 Cube 結果不同？

**原因：** 不同 Cube 的 Grain 不同。

| Cube | Grain | 在途任務數含義 |
|------|-------|---------------|
| ProcTaskNode | TASK_ID | 直接 COUNT 任務 |
| BizEventInfo | BIZ_EVENT_KEY | SUM(TASK_TODO_CNT + TASK_DOING_CNT) |

**建議：** 任務層級分析用 `ProcTaskNode`，業務事件層級分析用 `BizEventInfo`。

---

### Q4: 時間序列查詢為什麼沒有資料？

**原因：** 快照指標不適合做時間序列。

**快照指標（不適合時間序列）：**
- `inProgressTaskCount`
- `inProgressEventCount`
- `inProgressCount`
- `todoCount` / `doingCount`

**流量指標（適合時間序列）：**
- `doneCount` (按 endTime)
- `completedEventCount` (按 finalEndTime)
- `completedCount` (按 endTime)

---

### Q5: 為什麼平均值跨維度聚合結果不對？

**錯誤做法：**
```sql
-- 錯誤：將各 Plant 的平均處理時長平均
SELECT AVG(avg_work_duration) FROM plant_metrics
```

**正確做法：**
```sql
-- 正確：用總和/計數重新計算
SELECT SUM(total_work_duration) / SUM(done_count) FROM plant_metrics
```

**Cube.js 解法：** 同時查詢 `totalWorkDuration` 和 `doneCount`，前端計算。

---

### Q6: RMV 資料延遲問題

**現象：** 查詢結果與預期不符。

**原因：** RMV 每天 02:00 刷新，資料最多延遲 24 小時。

**解法：**
1. 確認 RMV 刷新狀態：`python scripts/check_rmv_status.py`
2. 如需即時資料，改用 View（效能較差）

---

### Q7: NULL 值處理

**現象：** 按維度分組時出現 NULL 行。

**原因：** 部分任務的 PLANT/DEPT_NAME/ASSIGNEE 為 NULL。

**解法：** 前端將 NULL 顯示為 'Unknown' 或 'Unassigned'。

---

## 八、API 呼叫範例

### 8.1 REST API

```bash
# 查詢在途任務數 by 廠區
curl "http://localhost:4002/cubejs-api/v1/load" \
  -H "Content-Type: application/json" \
  -d '{
    "measures": ["ProcTaskNode.inProgressTaskCount"],
    "dimensions": ["ProcTaskNode.plant"],
    "order": { "ProcTaskNode.inProgressTaskCount": "desc" }
  }'
```

### 8.2 JavaScript SDK

```javascript
import cubejs from '@cubejs-client/core';

const cubejsApi = cubejs('', {
  apiUrl: 'http://localhost:4002/cubejs-api/v1'
});

// 查詢在途任務數
const result = await cubejsApi.load({
  measures: ['ProcTaskNode.inProgressTaskCount'],
  dimensions: ['ProcTaskNode.plant']
});

console.log(result.tablePivot());
```

---

## 九、Playground 操作指南

1. 開啟 `http://localhost:4003`
2. 左側選擇 Cube（例如 `ProcTaskNode`）
3. 勾選 Measures（例如 `inProgressTaskCount`）
4. 勾選 Dimensions（例如 `plant`）
5. 點擊 `Run` 執行查詢
6. 可切換 Chart 類型查看不同視覺化

**常用查詢組合：**

| 目的 | Cube | Measures | Dimensions |
|------|------|----------|------------|
| 在途任務 by 廠區 | ProcTaskNode | inProgressTaskCount | plant |
| 任務狀態分布 | ProcTaskNode | todoCount, doingCount, doneCount | - |
| 自動完成率 by 流程 | ProcTaskNode | autoCompleteRate | procDefName |
| 在途業務事件 | BizEventInfo | inProgressEventCount | firstProcDefName |
| 流程數 by 狀態 | ProcInstNode | inProgressCount, completedCount | factory |
| 人員工作負荷 | ProcTaskNode | inProgressTaskCount | assignee |

---

**文件結束**
