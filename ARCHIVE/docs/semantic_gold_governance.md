# Semantic Gold 指標治理文件

**版本：** 1.0  
**更新日期：** 2026-01-12  
**適用範圍：** DMP Flowable Cube.js Model

---

## 一、Gold 指標清單

| 指標 | Cube | 定義 | 權威來源 |
|------|------|------|----------|
| `inProgressTaskCount` | ProcTaskNode | 狀態為 TODO 或 DOING 的任務數量 | ✅ 唯一 |
| `autoCompleteRate` | ProcTaskNode | DONE_AUTO / (DONE + DONE_AUTO) × 100% | ✅ 唯一 |
| `avgWorkDuration` | ProcTaskNode | 已完成任務 (DONE) 的處理時長平均值 | ✅ 唯一 |
| `inProgressEventCount` | BizEventInfo | 尚未完成的業務事件數量 | ✅ 唯一 |
| `avgTotalDuration` | BizEventInfo | 已完成業務事件的總歷時平均值 | ✅ 唯一 |
| `inProgressCount` | ProcInstNode | 尚未完成的流程實例數量 | ✅ 唯一 |
| `completedCount` | ProcInstNode | 已完成的流程實例數量 | ✅ 唯一 |

---

## 二、指標使用規範

### 2.1 在途任務數 (`ProcTaskNode.inProgressTaskCount`)

| 項目 | 規範 |
|------|------|
| 定義 | 狀態為 TODO 或 DOING 的任務數量 |
| 合法維度 | `plant`, `factory`, `lineName`, `deptName`, `assignee`, `procDefName` |
| 禁止維度 | `taskId`, `procInstId`, `businessKey` |
| 時間維度 | 不適用 (快照指標) |
| 聚合方式 | 可跨維度 SUM |

**正確用法：**
```json
{
  "measures": ["ProcTaskNode.inProgressTaskCount"],
  "dimensions": ["ProcTaskNode.plant"]
}
```

**錯誤用法：**
```json
// ❌ 錯誤：用 taskId 切分會得到無意義的 1:1 結果
{
  "measures": ["ProcTaskNode.inProgressTaskCount"],
  "dimensions": ["ProcTaskNode.taskId"]
}
```

---

### 2.2 自動完成率 (`ProcTaskNode.autoCompleteRate`)

| 項目 | 規範 |
|------|------|
| 定義 | DONE_AUTO / (DONE + DONE_AUTO) × 100% |
| 合法維度 | `plant`, `factory`, `procDefName` |
| 禁止維度 | `assignee` (自動完成無指派人員) |
| 時間維度 | `endTime` (week/month) |
| 聚合方式 | ⚠️ 不可直接平均 |

**正確用法（單一維度）：**
```json
{
  "measures": ["ProcTaskNode.autoCompleteRate"],
  "dimensions": ["ProcTaskNode.procDefName"]
}
```

**正確用法（跨維度聚合）：**
```json
// 查詢分子分母，前端重算
{
  "measures": ["ProcTaskNode.doneAutoForRate", "ProcTaskNode.doneTotalForRate"],
  "dimensions": ["ProcTaskNode.factory"]
}
// 前端計算: doneAutoForRate / doneTotalForRate * 100
```

**錯誤用法：**
```json
// ❌ 錯誤：直接平均各 Plant 的自動完成率
// 這會得到錯誤結果！
{
  "measures": ["ProcTaskNode.autoCompleteRate"],
  "dimensions": ["ProcTaskNode.factory"]
}
```

---

### 2.3 平均任務處理時長 (`ProcTaskNode.avgWorkDuration`)

| 項目 | 規範 |
|------|------|
| 定義 | 已完成任務 (DONE) 的處理時長平均值 |
| 合法維度 | `plant`, `factory`, `assignee`, `procDefName`, `taskName` |
| 時間維度 | `endTime` (week/month) |
| 聚合方式 | ⚠️ 不可直接平均 |

**正確用法（跨維度聚合）：**
```json
// 查詢總和與計數，前端重算
{
  "measures": ["ProcTaskNode.totalWorkDuration", "ProcTaskNode.doneCount"],
  "dimensions": ["ProcTaskNode.factory"]
}
// 前端計算: totalWorkDuration / doneCount
```

---

### 2.4 在途業務事件數 (`BizEventInfo.inProgressEventCount`)

| 項目 | 規範 |
|------|------|
| 定義 | 尚未完成的業務事件數量 |
| 合法維度 | `firstProcDefName` |
| 禁止維度 | `bizEventKey` |
| 時間維度 | 不適用 (快照指標) |
| 聚合方式 | 可跨維度 SUM |
| ⚠️ 限制 | 此 Cube 沒有廠區維度 |

**注意：** 如需按廠區分析業務事件，請用 `ProcTaskNode` 透過 `businessKey` 關聯。

---

### 2.5 平均業務事件總歷時 (`BizEventInfo.avgTotalDuration`)

| 項目 | 規範 |
|------|------|
| 定義 | 已完成業務事件的總歷時平均值 |
| 合法維度 | `firstProcDefName` |
| 時間維度 | `finalEndTime` (week/month) |
| 聚合方式 | ⚠️ 不可直接平均 |

**正確用法（跨維度聚合）：**
```json
{
  "measures": ["BizEventInfo.totalDurationSum", "BizEventInfo.completedEventCount"],
  "dimensions": ["BizEventInfo.firstProcDefName"]
}
// 前端計算: totalDurationSum / completedEventCount
```

---

## 三、avg / rate 指標聚合注意事項

### 3.1 問題說明

avg 和 rate 類指標在跨維度聚合時，不可直接平均或加總。

**錯誤範例：**
```
Plant A 自動完成率: 80% (8/10)
Plant B 自動完成率: 60% (6/10)
Factory 自動完成率: (80% + 60%) / 2 = 70% ❌ 錯誤！
Factory 自動完成率: (8+6) / (10+10) = 70% ✅ 正確
```

### 3.2 解決方案

每個 avg / rate 指標都提供對應的分子分母：

| 指標 | 分子 | 分母 |
|------|------|------|
| `autoCompleteRate` | `doneAutoForRate` | `doneTotalForRate` |
| `avgWorkDuration` | `totalWorkDuration` | `doneCount` |
| `avgTotalDuration` | `totalDurationSum` | `completedEventCount` |
| `avgDuration` | `totalDuration` | `completedCount` |

### 3.3 前端實作建議

```javascript
// 查詢分子分母
const result = await cubejsApi.load({
  measures: ['ProcTaskNode.doneAutoForRate', 'ProcTaskNode.doneTotalForRate'],
  dimensions: ['ProcTaskNode.factory']
});

// 前端計算正確的聚合值
const data = result.tablePivot().map(row => ({
  factory: row['ProcTaskNode.factory'],
  autoCompleteRate: row['ProcTaskNode.doneTotalForRate'] > 0 
    ? (row['ProcTaskNode.doneAutoForRate'] / row['ProcTaskNode.doneTotalForRate'] * 100).toFixed(2)
    : null
}));
```

---

## 四、新增指標前的檢查清單

在新增 Gold 指標前，請確認以下項目：

### 4.1 語意完整性
- [ ] 能用一句業務語言清楚描述
- [ ] 不依賴查詢者的理解
- [ ] 有明確的計數單位 (TASK_ID / PROC_INST_ID / BIZ_EVENT_KEY)

### 4.2 定義穩定性
- [ ] 不會因為多 join 一張表而改變數值
- [ ] 避免 row multiplication
- [ ] 來源是已聚合的 Silver RMV

### 4.3 使用約束
- [ ] 定義合法維度白名單
- [ ] 定義禁止維度黑名單
- [ ] 定義合法的 timeDimension 與 granularity
- [ ] 在 description 中明確標註

### 4.4 聚合方式
- [ ] 如果是 avg / rate，提供分子分母
- [ ] 在 description 中標註聚合警告
- [ ] 提供正確與錯誤的使用範例

### 4.5 唯一性
- [ ] 確認同一指標只存在於單一權威 Cube
- [ ] 如有類似指標，明確區分或移除

---

## 五、指標分類標記

| 標記 | 含義 |
|------|------|
| 🥇 | Gold 指標 - 核心業務指標，可對外使用 |
| 🥈 | Silver 包裝 - 輔助指標，標記 internal |
| (internal) | 僅供內部使用，不建議直接對外暴露 |

---

**文件結束**
