# L5 任務執行完成度 Dashboard 表格規格文件

## 📊 1️⃣ 表格 Schema 定義

### 🏭 維度欄位（左側固定欄位）

| 欄位名稱 | 說明 | 資料類型 | 限制 | 範例 |
|----------|------|----------|------|------|
| **flow_team** | 流程團隊 | String | 不可為空 | V1+V2+V3 |
| **region** | 地區 | String | 不可為空 | CNE |
| **plant** | 製造廠區 | String | 不可為空 | WJ2 |
| **factory** | 製造產品廠 | String | 不可為空 | NBU |
| **line** | 線體 | String | 可為空 | E5 |
| **vx_scope** | 任務類型範圍 | String | 僅允許 V1/V2/V3 或其組合 | V1, V2, V3, V1+V2+V3 |

### 📅 時間欄位設計（橫向欄位）

| 時間層級 | 說明 | 範例 | time_level | time_value |
|----------|------|------|------------|------------|
| **Day** | 日彙總 | 2025-12-25 ~ 2025-12-31 | 'Day' | '2025-12-25' |
| **Week** | 週彙總 | W51、W52、W1 | 'Week' | 'W51' |
| **Month** | 月彙總 | Dec | 'Month' | 'Dec' |

### 📋 任務狀態列（Row Schema）

| 任務狀態列 | 定義 | 說明 |
|------------|------|------|
| **Total Task** | 該時間區間內任務總數 | 所有狀態任務的總和 |
| **Todo** | 尚未開始之任務 | task_status = 'TODO' |
| **Doing** | 執行中之任務 | task_status = 'DOING' |
| **Done** | 已完成之任務 | task_status = 'DONE' |
| **Doing+Done** | 已處理任務總數 | Doing + Done |
| **Todo+Doing(Acc)** | 尚未完成之累積任務 | Todo + Doing |

### 🔢 每一格欄位 Schema（Task Qty + %）

| 欄位類型 | 說明 | 計算方式 | 範例 |
|----------|------|----------|------|
| **Task Qty** | 該狀態的任務數量 | COUNT | 150 |
| **(%)** | 該狀態佔 Total Task 比例 | 該狀態數 / Total Task × 100% | 75.0% |

---

## ⚙️ 2️⃣ 計算邏輯說明

### 🎯 資料來源優先順序

1. **Gold 層**：`gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV` （優先使用）
2. **Silver 層**：`silver.mv_fact_task_vx_attribution` （Gold 不足才補）
3. **Bronze 層**：`bronze.common_flowable_task_stats` （僅追溯，不可直接統計）

### 🔍 任務狀態判斷規則

```sql
-- 任務狀態分類
CASE 
    WHEN task_status = 'TODO' THEN 'Todo'
    WHEN task_status = 'DOING' THEN 'Doing'  
    WHEN task_status = 'DONE' THEN 'Done'
END

-- 排除條件（不納入計算）
WHERE task_bypass != 'Y'  -- 排除旁路任務
  AND task_definition_key NOT LIKE 'E%'  -- 排除系統節點任務
  AND task_definition_key NOT LIKE 'C%'  -- 排除非製造流程節點
```

### 🎯 Vx 類型歸屬規則

```sql
CASE 
    -- 優先級 1：工單號規則（最高優先級）
    WHEN mo_number LIKE '196%' OR mo_number LIKE '199%' 
         OR mo_number LIKE '200%' OR mo_number LIKE '210%' 
         OR mo_number LIKE '212%' OR mo_number LIKE '213%'
         OR mo_number LIKE '315%'
    THEN 'V1'
    
    -- 優先級 2：TaskDefinitionKey 前綴
    WHEN task_definition_key LIKE 'V1%' THEN 'V1'
    WHEN task_definition_key LIKE 'V2%' THEN 'V2'
    WHEN task_definition_key LIKE 'V3%' THEN 'V3'
    
    ELSE 'Unknown'
END AS vx_type
```

### 📊 聚合邏輯

```sql
-- 日聚合
GROUP BY snapshot_date, flow_team, region, plant, factory, line, vx_scope

-- 週聚合  
GROUP BY toISOWeek(snapshot_date), flow_team, region, plant, factory, line, vx_scope

-- 月聚合
GROUP BY toYYYYMM(snapshot_date), flow_team, region, plant, factory, line, vx_scope
```

---

## 🔧 3️⃣ ClickHouse SQL 範例

### 📅 Daily 查詢範例

```sql
-- 日彙總查詢
SELECT 
    snapshot_date,
    'Day' AS time_level,
    toString(snapshot_date) AS time_value,
    flow_team,
    region,
    plant,
    factory,
    line,
    vx_scope,
    
    -- 任務數量
    SUM(total_task_qty) AS total_tasks,
    SUM(todo_task_qty) AS todo_tasks,
    SUM(doing_task_qty) AS doing_tasks,
    SUM(done_task_qty) AS done_tasks,
    
    -- 比例計算
    ROUND(SUM(todo_task_qty) * 100.0 / SUM(total_task_qty), 2) AS todo_pct,
    ROUND(SUM(doing_task_qty) * 100.0 / SUM(total_task_qty), 2) AS doing_pct,
    ROUND(SUM(done_task_qty) * 100.0 / SUM(total_task_qty), 2) AS done_pct
    
FROM gold.vw_l5_dashboard_completion
WHERE time_level = 'Day'
  AND snapshot_date >= '2025-12-25'
  AND snapshot_date <= '2025-12-31'
GROUP BY snapshot_date, flow_team, region, plant, factory, line, vx_scope
ORDER BY snapshot_date DESC, region, plant, factory, line;
```

### 📅 Weekly 查詢範例

```sql
-- 週彙總查詢
SELECT 
    toISOWeek(snapshot_date) AS week_number,
    'Week' AS time_level,
    CONCAT('W', toString(toISOWeek(snapshot_date))) AS time_value,
    flow_team,
    region,
    plant,
    factory,
    line,
    vx_scope,
    
    -- 任務數量
    SUM(total_task_qty) AS total_tasks,
    SUM(todo_task_qty) AS todo_tasks,
    SUM(doing_task_qty) AS doing_tasks,
    SUM(done_task_qty) AS done_tasks,
    
    -- 比例計算
    ROUND(SUM(done_task_qty) * 100.0 / SUM(total_task_qty), 2) AS completion_rate
    
FROM gold.vw_l5_dashboard_completion
WHERE time_level = 'Week'
  AND snapshot_date >= '2025-12-01'
GROUP BY toISOWeek(snapshot_date), flow_team, region, plant, factory, line, vx_scope
ORDER BY week_number DESC, region, plant, factory, line;
```

### 📅 Monthly 查詢範例

```sql
-- 月彙總查詢
SELECT 
    toYYYYMM(snapshot_date) AS month_number,
    'Month' AS time_level,
    formatDateTime(snapshot_date, '%b') AS time_value,
    flow_team,
    region,
    plant,
    factory,
    line,
    vx_scope,
    
    -- 任務數量
    SUM(total_task_qty) AS total_tasks,
    SUM(todo_task_qty) AS todo_tasks,
    SUM(doing_task_qty) AS doing_tasks,
    SUM(done_task_qty) AS done_tasks,
    
    -- 組合狀態
    SUM(doing_task_qty + done_task_qty) AS doing_done_tasks,
    SUM(todo_task_qty + doing_task_qty) AS todo_doing_acc_tasks,
    
    -- 比例計算
    ROUND(SUM(done_task_qty) * 100.0 / SUM(total_task_qty), 2) AS completion_rate,
    ROUND((SUM(doing_task_qty) + SUM(done_task_qty)) * 100.0 / SUM(total_task_qty), 2) AS progress_rate
    
FROM gold.vw_l5_dashboard_completion
WHERE time_level = 'Month'
  AND snapshot_date >= '2025-11-01'
GROUP BY toYYYYMM(snapshot_date), flow_team, region, plant, factory, line, vx_scope
ORDER BY month_number DESC, region, plant, factory, line;
```

---

## 📊 4️⃣ 與 Dashboard 對應說明

### 🎨 Dashboard 區塊對應欄位

| Dashboard 區塊 | 對應欄位 | 查詢來源 | 說明 |
|----------------|----------|----------|------|
| **長條圖 - Todo/Doing/Done** | `todo_tasks`, `doing_tasks`, `done_tasks` | `gold.vw_l5_dashboard_charts` | 任務狀態分佈 |
| **折線圖 - Done Rate** | `overall_done_pct` | `gold.vw_l5_dashboard_charts` | 完成率趨勢 |
| **折線圖 - Doing+Done Rate** | `overall_progress_pct` | `gold.vw_l5_dashboard_charts` | 執行率趨勢 |
| **折線圖 - Todo+Doing(Acc)** | `overall_accumulation_pct` | `gold.vw_l5_dashboard_charts` | 累積率趨勢 |
| **下方明細表** | 全部欄位 | `gold.vw_l5_dashboard_completion` | 詳細維度分析 |

### 🎯 圖表配置建議

#### 上方圖表配置

```javascript
// 長條圖配置
{
  "chart_type": "stacked_bar",
  "x_axis": "time_value",
  "metrics": ["todo_tasks", "doing_tasks", "done_tasks"],
  "dimensions": ["vx_scope"],
  "filters": ["region", "plant", "time_level"]
}

// 折線圖配置
{
  "chart_type": "line",
  "x_axis": "time_value", 
  "metrics": ["overall_done_pct", "overall_progress_pct", "overall_accumulation_pct"],
  "dimensions": ["vx_scope"],
  "filters": ["region", "plant", "time_level"]
}
```

#### 下方明細表配置

```javascript
// 表格配置
{
  "chart_type": "table",
  "dimensions": ["region", "plant", "factory", "line", "vx_scope"],
  "metrics": [
    "total_task_qty", "todo_task_qty", "doing_task_qty", "done_task_qty",
    "todo_task_pct", "doing_task_pct", "done_task_pct"
  ],
  "filters": ["time_level", "time_value"]
}
```

---

## ✅ 5️⃣ 驗證條件

### 🔍 資料完整性驗證

```sql
-- 驗證 1：各狀態數量加總 = Total Task
SELECT 
    snapshot_date,
    region,
    plant,
    factory,
    line,
    vx_scope,
    total_task_qty,
    (todo_task_qty + doing_task_qty + done_task_qty) AS sum_check,
    CASE 
        WHEN total_task_qty = (todo_task_qty + doing_task_qty + done_task_qty) 
        THEN 'PASS' 
        ELSE 'FAIL' 
    END AS validation_result
FROM gold.vw_l5_dashboard_completion
WHERE time_level = 'Day'
HAVING validation_result = 'FAIL';
```

```sql
-- 驗證 2：各 % 欄位介於 0 ~ 100%
SELECT 
    snapshot_date,
    region,
    plant,
    factory,
    line,
    vx_scope,
    todo_task_pct,
    doing_task_pct,
    done_task_pct,
    CASE 
        WHEN todo_task_pct BETWEEN 0 AND 100 
         AND doing_task_pct BETWEEN 0 AND 100 
         AND done_task_pct BETWEEN 0 AND 100
        THEN 'PASS' 
        ELSE 'FAIL' 
    END AS percentage_validation
FROM gold.vw_l5_dashboard_completion
WHERE time_level = 'Day'
HAVING percentage_validation = 'FAIL';
```

```sql
-- 驗證 3：日 → 週 → 月 聚合數據一致性
WITH daily_sum AS (
    SELECT 
        toISOWeek(snapshot_date) AS week_num,
        vx_scope,
        SUM(total_task_qty) AS daily_total
    FROM gold.vw_l5_dashboard_completion
    WHERE time_level = 'Day'
      AND snapshot_date >= '2025-12-01'
    GROUP BY toISOWeek(snapshot_date), vx_scope
),
weekly_sum AS (
    SELECT 
        toISOWeek(snapshot_date) AS week_num,
        vx_scope,
        SUM(total_task_qty) AS weekly_total
    FROM gold.vw_l5_dashboard_completion
    WHERE time_level = 'Week'
      AND snapshot_date >= '2025-12-01'
    GROUP BY toISOWeek(snapshot_date), vx_scope
)
SELECT 
    d.week_num,
    d.vx_scope,
    d.daily_total,
    w.weekly_total,
    CASE 
        WHEN d.daily_total = w.weekly_total THEN 'PASS'
        ELSE 'FAIL'
    END AS consistency_check
FROM daily_sum d
LEFT JOIN weekly_sum w ON d.week_num = w.week_num AND d.vx_scope = w.vx_scope
WHERE consistency_check = 'FAIL';
```

### ⚠️ 已知限制說明

1. **去重影響**：週/月聚合可能因任務狀態變更導致輕微差異，屬正常現象
2. **Bronze 層限制**：不直接使用 Bronze 表統計，僅作追溯參考
3. **時間範圍**：建議查詢範圍不超過 3 個月，避免效能問題

---

## 🎯 完成：L5 任務執行完成度 Dashboard 表格

✅ **完成**：
📁 **SQL 檔案**：`sql/create_l5_dashboard_completion_table.sql`
📁 **規格文件**：`docs/l5_dashboard_completion_specification.md`
⚠️ **注意**：需執行 SQL 檔案建立彙總表，才能在 Dashboard 中使用