# Superset + Cube.js 聚合問題分析與解決方案

## 🎯 核心問題分析

### 問題根源：Superset 的聚合邏輯

**Superset 為什麼要求選擇聚合函數？**

1. **Superset 的設計邏輯**：Superset 把所有數值欄位都視為「原始數值」，需要聚合才能顯示
2. **即使是已聚合的結果**：Superset 不知道這些數值已經是聚合結果，仍會要求二次聚合
3. **GROUP BY 強制聚合**：當查詢包含維度（GROUP BY），Superset 強制要求所有數值欄位都要有聚合函數

### 當前 Cube.js 回傳的資料粒度

**你的 Gold 表粒度**：
```
每一列 = snapshot_date + region + plant + factory + line + vx_type 的組合
已經是聚合結果，不是明細資料
```

**Cube.js 回傳給 Superset 的粒度**：
```
根據 Superset 查詢的維度組合，可能會進一步聚合
例如：如果 Superset 只選 region + vx_type，Cube.js 會把多個 plant/factory/line 聚合起來
```

---

## 🔍 具體例子說明問題

### 場景：查看 CNE 地區的 V1 任務完成率

**Gold 表原始資料**：
```
snapshot_date | region | plant | factory | line | vx_type | completion_rate
2026-01-26   | CNE    | WJ2   | NBU     | E5   | V1      | 75.5
2026-01-26   | CNE    | WJ2   | NBU     | E6   | V1      | 80.2
2026-01-26   | CNE    | WJ3   | NPE     | L1   | V1      | 65.8
```

**Superset 查詢**：選擇 region + vx_type，要求 completion_rate

**如果選擇不同聚合函數的結果**：

1. **SUM(completion_rate)**：`75.5 + 80.2 + 65.8 = 221.5%` ❌ **錯誤！**
2. **AVG(completion_rate)**：`(75.5 + 80.2 + 65.8) / 3 = 73.8%` ⚠️ **可能錯誤**
3. **MAX(completion_rate)**：`80.2%` ❌ **語意錯誤**

**正確的計算應該是**：
```sql
-- 重新計算，基於任務數量加權平均
SUM(done_tasks) / SUM(total_tasks) * 100 = 正確的完成率
```

---

## 🚨 問題判斷：二次聚合問題

**你的情境是典型的「二次聚合問題」**：

1. **Gold 表已經聚合**：每列都是特定維度組合的聚合結果
2. **Superset 不知情**：把已聚合的數值當作原始數值處理
3. **強制二次聚合**：導致語意錯誤的結果

**特別是比例/百分比欄位**：
- `completion_rate` 已經是 `done_qty / total_qty * 100`
- Superset 再 SUM 或 AVG 會產生無意義的結果

---

## 💡 解決方案

### 方案 1：修改 Cube.js Schema（推薦）

**問題診斷**：你的 Cube schema 有問題

**當前錯誤寫法**：
```javascript
// ❌ 錯誤：對已聚合的比例再次聚合
completionRate: {
  type: `number`,
  sql: `CASE WHEN ${totalTask} > 0 THEN ${doneTask} * 100.0 / ${totalTask} ELSE 0 END`,
  title: '完成率 (%)',
  format: `percent`,
}
```

**正確寫法**：
```javascript
// ✅ 正確：使用加權平均計算比例
completionRate: {
  type: `number`,
  sql: `CASE WHEN SUM(sum_total_task_qty) > 0 THEN SUM(sum_done_qty) * 100.0 / SUM(sum_total_task_qty) ELSE 0 END`,
  title: '完成率 (%)',
  format: `percent`,
}

// 或者使用預計算的比例，但要加權平均
preCalculatedCompletionRate: {
  type: `number`,
  sql: `SUM(completion_rate * sum_total_task_qty) / SUM(sum_total_task_qty)`,
  title: '加權平均完成率 (%)',
  format: `percent`,
}
```

### 方案 2：調整 Gold 表粒度

**當前問題**：Gold 表粒度太細，包含已計算的比例

**建議調整**：
```sql
-- 選項 A：只存數量，不存比例
CREATE TABLE gold.L5_TASK_SUMMARY AS
SELECT 
    snapshot_date,
    region, plant, factory, line, vx_type,
    sum_total_task_qty,
    sum_todo_qty,
    sum_doing_qty, 
    sum_done_qty
    -- 不存 completion_rate，讓 Cube.js 動態計算
FROM ...

-- 選項 B：改成更粗粒度，避免二次聚合
CREATE TABLE gold.L5_TASK_SUMMARY_DAILY AS
SELECT 
    snapshot_date,
    vx_type,  -- 只保留必要維度
    SUM(sum_total_task_qty) as total_tasks,
    SUM(sum_done_qty) as done_tasks,
    SUM(sum_done_qty) * 100.0 / SUM(sum_total_task_qty) as completion_rate
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
GROUP BY snapshot_date, vx_type
```

### 方案 3：Superset 設定調整

**在 Superset Dataset 中設定**：

1. **數量欄位**：使用 `SUM`
   - `sum_total_task_qty` → SUM
   - `sum_done_qty` → SUM
   - `sum_doing_qty` → SUM

2. **比例欄位**：使用加權平均或自訂 SQL
   ```sql
   -- 在 Superset 中建立 Calculated Column
   SUM(sum_done_qty) * 100.0 / SUM(sum_total_task_qty)
   ```

3. **設定預設聚合**：
   - 在 Dataset 的 Columns 設定中，為每個欄位設定預設聚合函數
   - 避免使用者選錯聚合函數

---

## 🎯 推薦的最佳實踐

### 建議的 Gold 表設計

```sql
-- 建議：分離數量和比例
CREATE TABLE gold.L5_TASK_METRICS AS
SELECT 
    snapshot_date,
    region_code, plant_code, factory_code, line_code,
    vx_type,
    
    -- 只存可加總的數量
    sum_total_task_qty,
    sum_todo_qty,
    sum_doing_qty,
    sum_done_qty,
    
    -- 不存比例，讓 Cube.js 計算
    -- completion_rate,  -- 移除
    -- progress_rate     -- 移除
    
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
```

### 建議的 Cube.js Measures

```javascript
measures: {
  // ✅ 可加總的數量指標
  totalTask: {
    type: `sum`,
    sql: `sum_total_task_qty`,
  },
  
  doneTask: {
    type: `sum`, 
    sql: `sum_done_qty`,
  },
  
  // ✅ 正確的比例計算
  completionRate: {
    type: `number`,
    sql: `CASE WHEN SUM(sum_total_task_qty) > 0 
          THEN SUM(sum_done_qty) * 100.0 / SUM(sum_total_task_qty) 
          ELSE 0 END`,
    title: '完成率 (%)',
    format: `percent`,
  },
  
  // ❌ 避免這樣寫
  // wrongCompletionRate: {
  //   type: `avg`,  // 錯誤：對已聚合比例取平均
  //   sql: `completion_rate`,
  // }
}
```

### Superset 使用指南

**數量指標**：永遠使用 `SUM`
- totalTask → SUM
- doneTask → SUM  
- todoTask → SUM

**比例指標**：使用 Cube.js 計算的 measures
- completionRate → 直接使用（Cube.js 已正確計算）
- 不要在 Superset 中再次聚合比例欄位

**時間聚合**：
- 日 → 週：SUM 數量，重新計算比例
- 週 → 月：SUM 數量，重新計算比例

---

## 🔧 立即可行的修復

### 1. 修改你的 Cube.js Schema

<function_calls>
<invoke name="readFile">
<parameter name="path">cube/model/cubes/cube_gold_l5_task_completion.js

**檢查你的 Cube.js Schema**：

你的寫法是**正確的**！比例指標使用了正確的計算邏輯：

```javascript
// ✅ 你的寫法是正確的
doneRate: {
  type: `number`,
  sql: `CASE WHEN ${totalTask} > 0 THEN ${doneTask} * 100.0 / ${totalTask} ELSE 0 END`,
  title: 'Done 比例 (%)',
  format: `percent`,
}
```

這會讓 Cube.js 在聚合時正確計算比例。

### 2. Superset 正確使用方式

**對於你的 Cube measures，Superset 應該這樣選擇聚合**：

| Cube Measure | Superset 聚合 | 原因 |
|--------------|---------------|------|
| `totalTask` | **SUM** | 數量可加總 |
| `todoTask` | **SUM** | 數量可加總 |
| `doingTask` | **SUM** | 數量可加總 |
| `doneTask` | **SUM** | 數量可加總 |
| `doneRate` | **不需要選擇** | Cube.js 已計算 |
| `completionRate` | **不需要選擇** | Cube.js 已計算 |

**關鍵問題**：Superset 為什麼還要求選擇聚合？

### 3. 根本解決方案

**問題出在 Superset 的 Dataset 設定**：

1. **檢查 Superset Dataset**：
   - 進入 Dataset 設定
   - 檢查每個 Column 的 "Is Aggregation" 設定
   - 檢查 "Default Aggregation" 設定

2. **設定建議**：
   ```
   totalTask → Is Aggregation: No, Default: SUM
   doneTask → Is Aggregation: No, Default: SUM
   doneRate → Is Aggregation: Yes, Default: (不設定)
   ```

3. **或者在 Cube.js 中明確指定**：
   ```javascript
   doneRate: {
     type: `number`,
     sql: `CASE WHEN ${totalTask} > 0 THEN ${doneTask} * 100.0 / ${totalTask} ELSE 0 END`,
     title: 'Done 比例 (%)',
     format: `percent`,
     // 明確告訴 Superset 這是已聚合的指標
     meta: {
       superset: {
         is_aggregation: true
       }
     }
   }
   ```

---

## 🎯 最終建議

### 你應該採用的方案

**立即修復（最簡單）**：
1. **在 Superset 中**：
   - 數量指標選擇 `SUM`
   - 比例指標選擇 `AVG`（雖然不完美，但可用）

**中期優化（推薦）**：
1. **保持當前 Cube.js schema**（已經正確）
2. **在 Superset Dataset 中設定預設聚合**
3. **教育使用者正確選擇聚合函數**

**長期最佳實踐**：
1. **Gold 表只存數量，不存比例**
2. **所有比例都在 Cube.js 中動態計算**
3. **使用 Cube.js 的 preAggregations 提升效能**

### 具體操作步驟

**步驟 1：Superset Dataset 設定**
```
1. 進入 Superset → Datasets → 你的 L5DashboardCompletion
2. 點擊 "Edit Dataset"
3. 在 Columns 頁籤中：
   - totalTask: Default Aggregation = SUM
   - doneTask: Default Aggregation = SUM
   - doneRate: Default Aggregation = AVG (暫時)
4. 儲存設定
```

**步驟 2：建立圖表時**
```
- 選擇 Metrics 時，系統會自動套用預設聚合
- 不需要手動選擇聚合函數
```

**步驟 3：驗證結果**
```sql
-- 在 ClickHouse 中驗證
SELECT 
    vx_type,
    SUM(sum_total_task_qty) as total,
    SUM(sum_done_qty) as done,
    SUM(sum_done_qty) * 100.0 / SUM(sum_total_task_qty) as correct_rate
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
WHERE snapshot_date = '2026-01-26'
GROUP BY vx_type
```

---

## 📊 總結

**你的問題是**：「二次聚合問題」+ Superset 設定問題

**解決方案優先級**：
1. **立即**：在 Superset 中正確選擇聚合函數
2. **短期**：設定 Dataset 預設聚合
3. **長期**：優化 Gold 表設計

**你的 Cube.js schema 是正確的**，問題在於 Superset 的使用方式。