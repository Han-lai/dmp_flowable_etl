# 資料流程指南：Bronze → Silver → Metric

## 整體架構

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              MSSQL                                      │
│  APP_SRV_BPM (Flowable)  +  APP_SRV_COMMON (HR)                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                              JDBC Bridge
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Bronze Layer (原始)                             │
│  bpm_act_hi_procinst | bpm_act_hi_taskinst | bpm_act_hi_varinst        │
│  bpm_act_re_procdef  | common_hr_employee                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                           View / RMV 轉換
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Silver Layer (轉換)                             │
│                                                                         │
│  V_PROC_VARIABLES_PIVOTED ──┬──► V_HI_PROC_TASK_NODE (任務層)          │
│  V_TASK_VARIABLES_PIVOTED ──┘                                          │
│                                                                         │
│  V_PROC_VARIABLES_PIVOTED ──────► V_HI_PROCINST_NODE (流程層)          │
│                                                                         │
│  (直接聚合) ────────────────────► V_HI_BIZ_EVENT_INFO (業務事件層)     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                              直接查詢
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Metric (指標)                                 │
│  在途任務數 | 自動完成率 | 任務時長 | 依廠區/部門/人員分組              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 第一層：Bronze (原始資料)

### 資料來源

```
MSSQL (Flowable BPM) ──JDBC Bridge──► ClickHouse Bronze
```

### 使用的 5 張 Bronze 表

| 表 | 內容 | 關鍵欄位 |
|---|---|---|
| `bpm_act_hi_procinst` | 流程實例歷史 | PROC_INST_ID_, BUSINESS_KEY_, START_TIME_, END_TIME_, SUPER_PROCESS_INSTANCE_ID_ |
| `bpm_act_hi_taskinst` | 任務實例歷史 | ID_, PROC_INST_ID_, ASSIGNEE_, CLAIM_TIME_, END_TIME_, DELETE_REASON_ |
| `bpm_act_hi_varinst` | 流程變數 (EAV 格式) | PROC_INST_ID_, NAME_, TEXT_ |
| `bpm_act_re_procdef` | 流程定義 | ID_, NAME_, KEY_ |
| `common_hr_employee` | 員工資料 | EmpCode, DeptCodeLname |

---

## 第二層：Silver (轉換邏輯)

### 轉換順序與依賴

```
Bronze 表
    │
    ├─► V_PROC_VARIABLES_PIVOTED (行轉列，無依賴)
    │       varinst 的 EAV 格式 → 一列一個流程的所有變數
    │       Grain: PROC_INST_ID
    │
    ├─► V_TASK_VARIABLES_PIVOTED (行轉列，無依賴)
    │       任務層變數 (candidateUser, autoComplete)
    │       Grain: TASK_ID
    │
    ├─► V_HI_PROC_TASK_NODE (依賴上面兩個)
    │       JOIN: taskinst + procinst + proc_var + task_var + procdef + employee
    │       派生: TASK_STATUS, IDLE_DURATION_SEC, WORK_DURATION_SEC
    │       Grain: TASK_ID
    │
    ├─► V_HI_PROCINST_NODE (依賴 V_PROC_VARIABLES_PIVOTED)
    │       JOIN: procinst + proc_var + procdef
    │       派生: PROC_STATE, DEPTH, DURATION_SEC
    │       Grain: PROC_INST_ID
    │
    └─► V_HI_BIZ_EVENT_INFO (無依賴，直接聚合 Bronze)
            GROUP BY: BUSINESS_KEY
            聚合: 任務統計、時長統計
            Grain: BUSINESS_KEY
```

### Silver View 清單

| View | Grain | 用途 |
|------|-------|------|
| `V_PROC_VARIABLES_PIVOTED` | PROC_INST_ID | 流程變數樞紐化 (plant/factory/region) |
| `V_TASK_VARIABLES_PIVOTED` | TASK_ID | 任務變數樞紐化 (candidateUser/autoComplete) |
| `V_HI_PROC_TASK_NODE` | TASK_ID | 任務節點層，含狀態/時長/部門/廠區 |
| `V_HI_PROCINST_NODE` | PROC_INST_ID | 流程實例層，含階層/狀態 |
| `V_HI_BIZ_EVENT_INFO` | BUSINESS_KEY | 業務事件層，聚合統計 |

---

## 關鍵轉換邏輯

### 1. 流程變數樞紐化 (EAV → 寬表)

**原始 (EAV 格式)**
```
| PROC_INST_ID | NAME_   | TEXT_  |
|--------------|---------|--------|
| P001         | plant   | TPE    |
| P001         | factory | F01    |
| P001         | region  | TW     |
```

**轉換後 (寬表)**
```
| PROC_INST_ID | PLANT | FACTORY | REGION |
|--------------|-------|---------|--------|
| P001         | TPE   | F01     | TW     |
```

**SQL 邏輯**
```sql
SELECT
    PROC_INST_ID_ AS PROC_INST_ID,
    anyIf(TEXT_, NAME_ = 'plant') AS PLANT,
    anyIf(TEXT_, NAME_ = 'factory') AS FACTORY,
    anyIf(TEXT_, NAME_ = 'region') AS REGION
FROM bronze.bpm_act_hi_varinst
WHERE NAME_ IN ('plant', 'factory', 'region')
GROUP BY PROC_INST_ID_
```

### 2. TASK_STATUS (任務狀態判斷)

```sql
multiIf(
    DELETE_REASON_ IS NOT NULL AND DELETE_REASON_ != '', 'CANCELLED',
    ASSIGNEE_ IS NULL AND END_TIME_ IS NULL, 'TODO',
    ASSIGNEE_ IS NOT NULL AND END_TIME_ IS NULL, 'DOING',
    ASSIGNEE_ IS NOT NULL AND CLAIM_TIME_ IS NULL AND END_TIME_ IS NOT NULL, 'DONE_AUTO',
    END_TIME_ IS NOT NULL, 'DONE',
    'TODO'
)
```

| 狀態 | 條件 | 說明 |
|------|------|------|
| CANCELLED | DELETE_REASON 不為空 | 任務被取消/終止 |
| TODO | 無 ASSIGNEE 且無 END_TIME | 待辦 (未指派) |
| DOING | 有 ASSIGNEE 且無 END_TIME | 進行中 (已指派未完成) |
| DONE_AUTO | 有 ASSIGNEE、無 CLAIM_TIME、有 END_TIME | 自動完成 (被指派但沒認領就完成) |
| DONE | 有 END_TIME (其他情況) | 已完成 (有認領) |

### 3. 時長計算

```sql
-- 閒置時長：任務建立 → 被認領
IDLE_DURATION_SEC = dateDiff('second', START_TIME_, CLAIM_TIME_)

-- 處理時長：被認領 → 完成
WORK_DURATION_SEC = dateDiff('second', CLAIM_TIME_, END_TIME_)

-- 總時長：任務建立 → 完成
TOTAL_DURATION_SEC = dateDiff('second', START_TIME_, END_TIME_)
```

### 4. PROC_STATE (流程狀態判斷)

```sql
multiIf(
    DELETE_REASON_ IS NOT NULL AND DELETE_REASON_ != '', 'TERMINATED',
    END_TIME_ IS NOT NULL, 'DONE',
    'DOING'
)
```

### 5. DEPTH (流程階層深度)

```sql
if(SUPER_PROCESS_INSTANCE_ID_ IS NULL OR SUPER_PROCESS_INSTANCE_ID_ = '', 1, 2)
```

- DEPTH = 1：主流程
- DEPTH = 2：子流程

---

## 第三層：Metric (指標查詢)

### 指標與來源對照

| 指標 | 來源 View | 查詢邏輯 |
|------|-----------|----------|
| 在途任務總數 | V_HI_PROC_TASK_NODE | `WHERE TASK_STATUS IN ('TODO','DOING')` |
| 在途業務事件數 | V_HI_BIZ_EVENT_INFO | `WHERE FINAL_END_TIME IS NULL` |
| 自動完成率 | V_HI_PROC_TASK_NODE | `DONE_AUTO / (DONE + DONE_AUTO)` |
| 任務閒置時長 | V_HI_PROC_TASK_NODE | `IDLE_DURATION_SEC` |
| 任務處理時長 | V_HI_PROC_TASK_NODE | `WORK_DURATION_SEC` |
| 依廠區分組 | V_HI_PROC_TASK_NODE | `GROUP BY PLANT` |
| 依部門分組 | V_HI_PROC_TASK_NODE | `GROUP BY DEPT_NAME` |
| 依人員分組 | V_HI_PROC_TASK_NODE | `GROUP BY ASSIGNEE` |
| 流程總歷時 | V_HI_PROCINST_NODE | `DURATION_SEC` |
| 業務事件總歷時 | V_HI_BIZ_EVENT_INFO | `TOTAL_DURATION_SEC` |

### 查詢範例

**在途任務總數**
```sql
SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE 
WHERE TASK_STATUS IN ('TODO', 'DOING')
```

**自動完成率**
```sql
SELECT round(
    countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / 
    countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2
) AS auto_rate
FROM silver.V_HI_PROC_TASK_NODE
```

**依廠區分組的在途任務數**
```sql
SELECT PLANT, count(*) AS TASK_CNT
FROM silver.V_HI_PROC_TASK_NODE
WHERE TASK_STATUS IN ('TODO', 'DOING')
GROUP BY PLANT
ORDER BY TASK_CNT DESC
```

---

## View vs RMV 選擇

| 場景 | 建議 | 原因 |
|------|------|------|
| 即時查詢、資料需最新 | View (V_*) | 每次查詢即時計算 |
| 報表查詢、效能優先 | RMV (RMV_*) | 預先計算，查詢快 4-10 倍 |

RMV 每天 02:00 自動刷新，資料最多延遲 24 小時。

---

## 相關檔案

| 檔案 | 用途 |
|------|------|
| `sql/05_create_silver_views.sql` | Silver View DDL |
| `sql/06_create_silver_rmv.sql` | Silver RMV DDL |
| `scripts/query_metrics.py` | 指標查詢 (View) |
| `scripts/query_metrics_rmv.py` | 指標查詢 (RMV) |
| `docs/metric_query_summary.md` | 指標查詢統整 |
