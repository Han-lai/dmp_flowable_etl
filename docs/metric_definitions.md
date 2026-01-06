# 流程指標業務定義文件 (Metric Definition Document)

**版本：** 1.0  
**更新日期：** 2026-01-02  
**適用範圍：** DMP Flowable 流程分析系統

---

## 維度階層關係

```
FACTORY (工廠)
  └── PLANT (產品線)
        └── LINE_NAME (線別)
```

**說明：**
- 一個 FACTORY 包含多個 PLANT
- 一個 PLANT 包含多個 LINE_NAME
- 流程實例（PROC_INST_ID）在建立時會綁定到特定的 FACTORY / PLANT / LINE_NAME

---

## 指標分類架構

| 分類 | 指標數 | 說明 |
|------|--------|------|
| **存量指標** | 2 | 描述「當下有多少」（快照） |
| **比率指標** | 1 | 描述「佔比關係」 |
| **分布指標** | 1 | 描述「狀態分布」 |
| **維度分析** | 4 | 按不同維度切分的存量 |
| **時長指標** | 2 | 描述「平均耗時」 |
| **健康度指標** | 2 | 描述「流程健康狀況」 |

---

## 指標定義

### 📊 存量指標 (Stock Metrics)

#### 1. 在途業務事件總數

**業務定義：**  
截至查詢時點，尚未完成的業務事件數量。一個業務事件（BUSINESS_KEY）代表一個完整的業務流程實例，可能包含多個子流程和任務。

**業務現象：**  
反映系統中「正在處理中」的業務量，是衡量系統負載的核心指標。

**計數單位：** BUSINESS_KEY（業務事件唯一識別碼）

**主要分析層級：**
- ✅ FACTORY 層級：適合，可安全聚合
- ✅ PLANT 層級：適合，可安全聚合
- ✅ LINE_NAME 層級：適合，可安全聚合

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標，只能取特定時點值）
- **跨維度聚合：** 可加總（SUM）
  - Factory 值 = 該 Factory 下所有 Plant 的加總
  - Plant 值 = 該 Plant 下所有 Line 的加總

**去重邏輯：**
- 按 BUSINESS_KEY 去重（一個業務事件只計算一次）
- 跨 Line 彙總到 Plant 時：`COUNT(DISTINCT BUSINESS_KEY)`
- 跨 Plant 彙總到 Factory 時：`COUNT(DISTINCT BUSINESS_KEY)`

**歷史趨勢分析：**
- 需要每日快照（每天記錄當日的在途數量）
- 趨勢圖顯示：每日在途量變化
- 不可將多日數值相加

**注意事項：**
- ⚠️ 此為時點指標，不同時點的值不可相加
- ⚠️ 必須確保 BUSINESS_KEY 在 FACTORY/PLANT/LINE_NAME 維度上唯一歸屬

---

#### 2. 在途任務總數

**業務定義：**  
截至查詢時點，所有在途業務事件中，狀態為「待辦（TODO）」或「處理中（DOING）」的任務總數。

**業務現象：**  
反映系統中「待處理」和「處理中」的任務量，是衡量人員工作負荷的指標。

**計數單位：** TASK_ID（任務唯一識別碼）

**主要分析層級：**
- ✅ FACTORY 層級：適合，可安全聚合
- ✅ PLANT 層級：適合，可安全聚合
- ✅ LINE_NAME 層級：適合，可安全聚合
- ✅ ASSIGNEE 層級：適合（人員維度）

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 可加總（SUM）
  - Factory 值 = 該 Factory 下所有 Plant 的加總
  - Plant 值 = 該 Plant 下所有 Line 的加總

**去重邏輯：**
- 按 TASK_ID 去重（一個任務只計算一次）
- 跨 Line 彙總到 Plant 時：`COUNT(DISTINCT TASK_ID WHERE TASK_STATUS IN ('TODO', 'DOING'))`
- 跨 Plant 彙總到 Factory 時：`COUNT(DISTINCT TASK_ID WHERE TASK_STATUS IN ('TODO', 'DOING'))`

**歷史趨勢分析：**
- 需要每日快照
- 可分析：每日在途任務量變化、人員負荷趨勢

**注意事項：**
- ⚠️ 此為時點指標，不同時點的值不可相加
- ⚠️ 一個業務事件可能包含多個任務，因此「在途任務數」通常大於「在途業務事件數」

---

### 📈 比率指標 (Ratio Metrics)

#### 3. 事件自動完成率

**業務定義：**  
在所有已完成的任務中，自動完成（DONE_AUTO）的任務佔比。反映流程自動化程度。

**業務現象：**  
衡量流程自動化效率，比率越高代表人工介入越少。

**計算邏輯：**  
```
自動完成率 = DONE_AUTO 任務數 / (DONE + DONE_AUTO) 任務數 × 100%
```

**主要分析層級：**
- ✅ FACTORY 層級：適合
- ✅ PLANT 層級：適合
- ✅ LINE_NAME 層級：適合
- ✅ PROC_DEF_NAME 層級：適合（流程維度）

**聚合原則：**
- **跨時間聚合：** 可加權平均
  - 月平均 = Σ(每日 DONE_AUTO 數) / Σ(每日 DONE + DONE_AUTO 數)
- **跨維度聚合：** 需重新計算，不可直接平均
  - Factory 自動完成率 = Σ(該 Factory 下所有 DONE_AUTO) / Σ(該 Factory 下所有 DONE + DONE_AUTO)
  - ❌ 錯誤：將各 Plant 的自動完成率平均

**去重邏輯：**
- 按 TASK_ID 去重
- 跨 Line 彙總到 Plant 時：
  ```
  SUM(DONE_AUTO 任務數) / SUM(DONE + DONE_AUTO 任務數)
  ```

**歷史趨勢分析：**
- 可按日/週/月計算自動完成率
- 趨勢圖顯示：自動化程度變化

**注意事項：**
- ⚠️ 不可將各維度的比率直接平均，必須用分子分母重新計算
- ⚠️ 只計算已完成任務（DONE + DONE_AUTO），不包含 TODO / DOING / CANCELLED

---

### 📊 分布指標 (Distribution Metrics)

#### 4. TASK_STATUS 分布

**業務定義：**  
所有任務按狀態（TODO / DOING / DONE / DONE_AUTO / CANCELLED）的數量分布。

**業務現象：**  
反映任務生命週期的整體狀態分布，用於健康度檢查。

**計數單位：** TASK_ID

**主要分析層級：**
- ✅ 全局層級：適合（查看整體分布）
- ✅ FACTORY 層級：適合
- ✅ PLANT 層級：適合
- ✅ LINE_NAME 層級：適合

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 可加總（SUM）
  - Factory 各狀態數 = 該 Factory 下所有 Plant 的各狀態數加總

**去重邏輯：**
- 按 TASK_ID 去重
- 跨 Line 彙總到 Plant 時：`COUNT(DISTINCT TASK_ID) GROUP BY TASK_STATUS`

**歷史趨勢分析：**
- 需要每日快照
- 可分析：各狀態佔比變化、異常狀態（CANCELLED）增長趨勢

**注意事項：**
- ⚠️ 此為時點指標，記錄當下的狀態分布
- ⚠️ 各狀態數量加總應等於總任務數

---

### 🔍 維度分析指標 (Dimensional Analysis Metrics)

#### 5. 在途任務數 - 依廠區 (PLANT)

**業務定義：**  
按 PLANT（產品線）維度，統計各 PLANT 的在途任務數（TODO + DOING）。

**業務現象：**  
識別哪些產品線的任務負荷較重，用於資源調配。

**計數單位：** TASK_ID

**主要分析層級：**
- ✅ PLANT 層級：主要分析層級
- ⚠️ FACTORY 層級：需先按 PLANT 分組，再彙總到 FACTORY
- ⚠️ LINE_NAME 層級：可進一步下鑽

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 
  - PLANT → FACTORY：`SUM(各 PLANT 的在途任務數) GROUP BY FACTORY`

**去重邏輯：**
- 按 TASK_ID 去重
- 一個任務只歸屬於一個 PLANT

**歷史趨勢分析：**
- 需要每日快照
- 可分析：各 PLANT 負荷變化、識別瓶頸產品線

**注意事項：**
- ⚠️ 如果 PLANT 為 NULL，需歸類為 'Unknown' 並單獨統計
- ⚠️ 各 PLANT 的在途任務數加總應等於「在途任務總數」

---

#### 6. 在途任務數 - 依部門 (DEPT_NAME)

**業務定義：**  
按部門維度，統計各部門的在途任務數（TODO + DOING）。

**業務現象：**  
識別哪些部門的任務負荷較重，用於人力資源調配。

**計數單位：** TASK_ID

**主要分析層級：**
- ✅ DEPT_NAME 層級：主要分析層級
- ⚠️ 不適合按 FACTORY/PLANT/LINE_NAME 聚合（部門是組織維度，與產線維度正交）

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 
  - 部門維度與產線維度正交，不建議混合聚合

**去重邏輯：**
- 按 TASK_ID 去重
- 一個任務只歸屬於一個部門（由 ASSIGNEE 的部門決定）

**歷史趨勢分析：**
- 需要每日快照
- 可分析：各部門負荷變化、識別人力瓶頸

**注意事項：**
- ⚠️ 部門資訊來自 ASSIGNEE 的所屬部門，如果任務未指派（ASSIGNEE IS NULL），則 DEPT_NAME 為 NULL
- ⚠️ 此指標與 FACTORY/PLANT/LINE_NAME 維度獨立，不建議混合分析

---

#### 7. 在途任務數 - 依人員 (ASSIGNEE)

**業務定義：**  
按人員維度，統計各人員的在途任務數（TODO + DOING）。

**業務現象：**  
識別個人工作負荷，用於任務分配平衡。

**計數單位：** TASK_ID

**主要分析層級：**
- ✅ ASSIGNEE 層級：主要分析層級
- ⚠️ 可彙總到 DEPT_NAME 層級
- ⚠️ 不適合按 FACTORY/PLANT/LINE_NAME 聚合（人員維度與產線維度正交）

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 
  - ASSIGNEE → DEPT_NAME：`SUM(各人員的在途任務數) GROUP BY DEPT_NAME`

**去重邏輯：**
- 按 TASK_ID 去重
- 一個任務只歸屬於一個 ASSIGNEE

**歷史趨勢分析：**
- 需要每日快照
- 可分析：個人負荷變化、識別過載人員

**注意事項：**
- ⚠️ 未指派任務（ASSIGNEE IS NULL）需歸類為 'Unassigned'
- ⚠️ 此指標與 FACTORY/PLANT/LINE_NAME 維度獨立

---

#### 10. 在途流程健康度快照 (Top 10)

**業務定義：**  
按流程定義（PROC_DEF_NAME）維度，統計各流程的在途業務事件數，取前 10 名。

**業務現象：**  
識別哪些流程類型的在途量最多，用於流程優化優先級判斷。

**計數單位：** BUSINESS_KEY

**主要分析層級：**
- ✅ PROC_DEF_NAME 層級：主要分析層級
- ⚠️ 可進一步按 FACTORY/PLANT/LINE_NAME 分組

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 
  - 可按 FACTORY/PLANT/LINE_NAME 分組後，再按 PROC_DEF_NAME 統計

**去重邏輯：**
- 按 BUSINESS_KEY 去重
- 一個業務事件只歸屬於一個流程定義

**歷史趨勢分析：**
- 需要每日快照
- 可分析：各流程在途量變化、識別瓶頸流程

**注意事項：**
- ⚠️ 只取 Top 10，完整分析需移除 LIMIT
- ⚠️ 流程定義維度與產線維度可交叉分析

---

### ⏱️ 時長指標 (Duration Metrics)

#### 8. 平均業務事件總歷時 (秒)

**業務定義：**  
所有已完成業務事件的總歷時（從第一個任務開始到最後一個任務結束）的平均值。

**業務現象：**  
反映業務流程的整體效率，歷時越短代表流程越順暢。

**計算單位：** 秒

**主要分析層級：**
- ✅ FACTORY 層級：適合
- ✅ PLANT 層級：適合
- ✅ LINE_NAME 層級：適合
- ✅ PROC_DEF_NAME 層級：適合（流程維度）

**聚合原則：**
- **跨時間聚合：** 可加權平均
  - 月平均 = Σ(每日總歷時) / Σ(每日完成事件數)
- **跨維度聚合：** 需重新計算，不可直接平均
  - Factory 平均歷時 = Σ(該 Factory 下所有事件總歷時) / Σ(該 Factory 下完成事件數)
  - ❌ 錯誤：將各 Plant 的平均歷時平均

**去重邏輯：**
- 按 BUSINESS_KEY 去重
- 只計算已完成事件（FINAL_END_TIME IS NOT NULL）

**歷史趨勢分析：**
- 可按日/週/月計算平均歷時
- 趨勢圖顯示：流程效率變化

**注意事項：**
- ⚠️ 不可將各維度的平均值直接平均，必須用總歷時/事件數重新計算
- ⚠️ 只計算已完成事件，在途事件不納入

---

#### 9. 平均任務處理時長 (秒)

**業務定義：**  
所有已完成任務（DONE）的處理時長（從 CLAIM_TIME 到 END_TIME）的平均值。

**業務現象：**  
反映人員處理任務的效率，處理時長越短代表效率越高。

**計算單位：** 秒

**主要分析層級：**
- ✅ FACTORY 層級：適合
- ✅ PLANT 層級：適合
- ✅ LINE_NAME 層級：適合
- ✅ ASSIGNEE 層級：適合（人員維度）
- ✅ PROC_DEF_NAME 層級：適合（流程維度）

**聚合原則：**
- **跨時間聚合：** 可加權平均
  - 月平均 = Σ(每日總處理時長) / Σ(每日完成任務數)
- **跨維度聚合：** 需重新計算，不可直接平均
  - Factory 平均處理時長 = Σ(該 Factory 下所有任務處理時長) / Σ(該 Factory 下完成任務數)

**去重邏輯：**
- 按 TASK_ID 去重
- 只計算已完成任務（TASK_STATUS = 'DONE'）

**歷史趨勢分析：**
- 可按日/週/月計算平均處理時長
- 可分析：人員效率變化、流程瓶頸識別

**注意事項：**
- ⚠️ 不可將各維度的平均值直接平均
- ⚠️ 只計算 DONE 狀態，不包含 DONE_AUTO（自動完成無處理時長）

---

### 🏥 健康度指標 (Health Metrics)

#### 11. 依流程的自動完成率 (Top 10)

**業務定義：**  
按流程定義（PROC_DEF_NAME）維度，計算各流程的自動完成率，取前 10 名。

**業務現象：**  
識別哪些流程的自動化程度最高，用於自動化推廣參考。

**計算邏輯：**  
```
流程自動完成率 = 該流程的 DONE_AUTO 任務數 / 該流程的 (DONE + DONE_AUTO) 任務數 × 100%
```

**主要分析層級：**
- ✅ PROC_DEF_NAME 層級：主要分析層級
- ⚠️ 可進一步按 FACTORY/PLANT/LINE_NAME 分組

**聚合原則：**
- **跨時間聚合：** 可加權平均
- **跨維度聚合：** 需重新計算
  - Factory 層級某流程的自動完成率 = Σ(該 Factory 下該流程的 DONE_AUTO) / Σ(該 Factory 下該流程的 DONE + DONE_AUTO)

**去重邏輯：**
- 按 TASK_ID 去重
- 只計算已完成任務（DONE + DONE_AUTO）

**歷史趨勢分析：**
- 可按日/週/月計算各流程自動完成率
- 可分析：自動化推進效果

**注意事項：**
- ⚠️ 只取 Top 10，完整分析需移除 LIMIT
- ⚠️ 需設定最小樣本數（如：完成任務數 >= 10）避免小樣本偏差

---

## 指標聚合矩陣

| 指標 | 跨時間聚合 | 跨 LINE 聚合 | 跨 PLANT 聚合 | 跨 FACTORY 聚合 |
|------|-----------|-------------|--------------|----------------|
| 在途業務事件總數 | ❌ 快照 | ✅ SUM | ✅ SUM | ✅ SUM |
| 在途任務總數 | ❌ 快照 | ✅ SUM | ✅ SUM | ✅ SUM |
| 事件自動完成率 | ✅ 加權平均 | ⚠️ 重新計算 | ⚠️ 重新計算 | ⚠️ 重新計算 |
| TASK_STATUS 分布 | ❌ 快照 | ✅ SUM | ✅ SUM | ✅ SUM |
| 在途任務數-依廠區 | ❌ 快照 | ✅ SUM | ✅ SUM | ✅ SUM |
| 在途任務數-依部門 | ❌ 快照 | N/A | N/A | N/A |
| 在途任務數-依人員 | ❌ 快照 | N/A | N/A | N/A |
| 平均業務事件總歷時 | ✅ 加權平均 | ⚠️ 重新計算 | ⚠️ 重新計算 | ⚠️ 重新計算 |
| 平均任務處理時長 | ✅ 加權平均 | ⚠️ 重新計算 | ⚠️ 重新計算 | ⚠️ 重新計算 |
| 在途流程健康度快照 | ❌ 快照 | ✅ SUM | ✅ SUM | ✅ SUM |
| 依流程的自動完成率 | ✅ 加權平均 | ⚠️ 重新計算 | ⚠️ 重新計算 | ⚠️ 重新計算 |

**圖例：**
- ✅ 可直接聚合
- ⚠️ 需重新計算（不可直接平均或加總）
- ❌ 不可聚合
- N/A 維度不適用

---

## Gold 層 MVIEW 設計建議

### 方案：每日快照表 + 維度預聚合

```sql
CREATE MATERIALIZED VIEW gold.daily_metrics_snapshot
REFRESH EVERY 1 DAY
AS
SELECT
    today() AS snapshot_date,
    FACTORY,
    PLANT,
    LINE_NAME,
    PROC_DEF_NAME,
    
    -- 存量指標（快照）
    COUNT(DISTINCT CASE WHEN FINAL_END_TIME IS NULL THEN BUSINESS_KEY END) AS in_progress_events,
    COUNT(DISTINCT CASE WHEN TASK_STATUS IN ('TODO', 'DOING') THEN TASK_ID END) AS in_progress_tasks,
    
    -- 比率指標（分子分母分開存）
    COUNT(DISTINCT CASE WHEN TASK_STATUS = 'DONE_AUTO' THEN TASK_ID END) AS done_auto_tasks,
    COUNT(DISTINCT CASE WHEN TASK_STATUS IN ('DONE', 'DONE_AUTO') THEN TASK_ID END) AS done_total_tasks,
    
    -- 時長指標（總和 + 計數，用於計算平均）
    SUM(CASE WHEN FINAL_END_TIME IS NOT NULL THEN TOTAL_DURATION_SEC ELSE 0 END) AS total_event_duration_sec,
    COUNT(DISTINCT CASE WHEN FINAL_END_TIME IS NOT NULL THEN BUSINESS_KEY END) AS completed_events,
    
    SUM(CASE WHEN TASK_STATUS = 'DONE' THEN WORK_DURATION_SEC ELSE 0 END) AS total_work_duration_sec,
    COUNT(DISTINCT CASE WHEN TASK_STATUS = 'DONE' THEN TASK_ID END) AS done_tasks
    
FROM silver.RMV_HI_PROC_TASK_NODE
LEFT JOIN silver.RMV_HI_BIZ_EVENT_INFO USING (BUSINESS_KEY)
GROUP BY snapshot_date, FACTORY, PLANT, LINE_NAME, PROC_DEF_NAME
```

**優點：**
- 每日快照，支援歷史趨勢分析
- 分子分母分開存，支援任意維度重新計算比率
- 預聚合到最細粒度，查詢時可靈活彙總

---

## 使用範例

### 查詢 Factory 層級的在途任務數（跨 Plant 聚合）

```sql
SELECT 
    FACTORY,
    SUM(in_progress_tasks) AS total_in_progress_tasks
FROM gold.daily_metrics_snapshot
WHERE snapshot_date = today()
GROUP BY FACTORY
ORDER BY total_in_progress_tasks DESC
```

### 查詢 Factory 層級的自動完成率（重新計算）

```sql
SELECT 
    FACTORY,
    SUM(done_auto_tasks) AS auto_tasks,
    SUM(done_total_tasks) AS total_tasks,
    ROUND(SUM(done_auto_tasks) * 100.0 / SUM(done_total_tasks), 2) AS auto_rate_pct
FROM gold.daily_metrics_snapshot
WHERE snapshot_date = today()
GROUP BY FACTORY
ORDER BY auto_rate_pct DESC
```

### 查詢過去 30 天的在途任務趨勢（Factory 層級）

```sql
SELECT 
    snapshot_date,
    FACTORY,
    SUM(in_progress_tasks) AS total_in_progress_tasks
FROM gold.daily_metrics_snapshot
WHERE snapshot_date >= today() - INTERVAL 30 DAY
GROUP BY snapshot_date, FACTORY
ORDER BY snapshot_date, FACTORY
```

---

## 附錄：常見錯誤與避免方法

### ❌ 錯誤 1：直接平均比率指標

```sql
-- 錯誤：將各 Plant 的自動完成率平均
SELECT AVG(auto_rate_pct) FROM plant_metrics
```

**正確做法：**
```sql
-- 正確：用分子分母重新計算
SELECT SUM(done_auto_tasks) * 100.0 / SUM(done_total_tasks) AS auto_rate_pct
FROM plant_metrics
```

---

### ❌ 錯誤 2：跨時間加總快照指標

```sql
-- 錯誤：將每日在途任務數相加
SELECT SUM(in_progress_tasks) FROM daily_snapshot
WHERE snapshot_date BETWEEN '2026-01-01' AND '2026-01-31'
```

**正確做法：**
```sql
-- 正確：顯示每日趨勢，不相加
SELECT snapshot_date, in_progress_tasks FROM daily_snapshot
WHERE snapshot_date BETWEEN '2026-01-01' AND '2026-01-31'
ORDER BY snapshot_date
```

---

### ❌ 錯誤 3：忽略 NULL 值導致重複計算

```sql
-- 錯誤：未處理 PLANT IS NULL 的情況
SELECT PLANT, COUNT(*) FROM tasks GROUP BY PLANT
```

**正確做法：**
```sql
-- 正確：將 NULL 歸類為 'Unknown'
SELECT COALESCE(PLANT, 'Unknown') AS PLANT, COUNT(*) FROM tasks GROUP BY PLANT
```

---

**文件結束**
