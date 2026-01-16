# Silver Layer 架構文件

## 表格統計

| 層級 | 類型 | 數量 |
|------|------|------|
| Bronze | Table | 16 張 (使用 5 張) |
| Silver | View | 4 張 |

---

## Bronze 表 (16 張)

### 使用中 (5 張)

| 表名 | 用途 | 關鍵欄位 |
|------|------|---------|
| `bpm_act_hi_procinst` | 流程實例歷史 | PROC_INST_ID_, BUSINESS_KEY_, START_TIME_, END_TIME_, SUPER_PROCESS_INSTANCE_ID_ |
| `bpm_act_hi_taskinst` | 任務實例歷史 | ID_, PROC_INST_ID_, ASSIGNEE_, CLAIM_TIME_, END_TIME_, DELETE_REASON_ |
| `bpm_act_hi_varinst` | 流程變數 | PROC_INST_ID_, NAME_, TEXT_ (plant/factory/region) |
| `bpm_act_re_procdef` | 流程定義 | ID_, NAME_ |
| `common_hr_employee` | 員工資料 | EmpCode, DeptCodeLname |

### 未使用 (11 張)
其他 BPM 和 Common 相關表

---

## Silver View (4 張)

| View | Grain | 用途 |
|------|-------|------|
| `V_PROC_VARIABLES_PIVOTED` | PROC_INST_ID | 流程變數樞紐化 (plant/factory/region/sapPlant/lineName/modelName) |
| `V_HI_PROC_TASK_NODE` | TASK_ID | 任務節點層，含狀態/時長/部門/廠區 |
| `V_HI_PROCINST_NODE` | PROC_INST_ID | 流程實例層，含階層/狀態 |
| `V_HI_BIZ_EVENT_INFO` | BUSINESS_KEY | 業務事件層，聚合統計 |

---

## 關係圖

```
Bronze Layer                          Silver Layer
─────────────────────────────────────────────────────────────────
bpm_act_hi_varinst ──────────────────► V_PROC_VARIABLES_PIVOTED
                                              │
                                              ▼
bpm_act_hi_taskinst ──┬──────────────► V_HI_PROC_TASK_NODE
bpm_act_hi_procinst ──┤                       
bpm_act_re_procdef  ──┤                       
common_hr_employee  ──┘                       
                                              
bpm_act_hi_procinst ──┬──────────────► V_HI_PROCINST_NODE
bpm_act_re_procdef  ──┘                       
                                              
bpm_act_hi_procinst ──┬──────────────► V_HI_BIZ_EVENT_INFO
bpm_act_hi_taskinst ──┤
bpm_act_re_procdef  ──┘
```

---

## View 建立順序 (有依賴關係)

```
1. V_PROC_VARIABLES_PIVOTED   (無依賴，來源: varinst)
       │
       ▼
2. V_HI_PROC_TASK_NODE        (依賴 1)
3. V_HI_PROCINST_NODE         (依賴 1)
4. V_HI_BIZ_EVENT_INFO        (無依賴，直接查 Bronze)
```

---

## View 欄位說明

### V_PROC_VARIABLES_PIVOTED
將 varinst 的行轉列，方便後續 JOIN

| 欄位 | 來源 |
|------|------|
| PROC_INST_ID | varinst.PROC_INST_ID_ |
| PLANT | NAME_ = 'plant' |
| FACTORY | NAME_ = 'factory' |
| REGION | NAME_ = 'region' |
| SAP_PLANT | NAME_ = 'sapPlant' |
| LINE_NAME | NAME_ = 'lineName' |
| MODEL_NAME | NAME_ = 'modelName' |

### V_HI_PROC_TASK_NODE
任務節點層，含狀態/時長/部門/廠區

| 欄位 | 說明 |
|------|------|
| TASK_ID | 任務 ID |
| TASK_STATUS | TODO/DOING/DONE/DONE_AUTO/CANCELLED |
| IDLE_DURATION_SEC | 閒置時長 (START → CLAIM) |
| WORK_DURATION_SEC | 處理時長 (CLAIM → END) |
| TOTAL_DURATION_SEC | 總時長 (START → END) |
| PLANT/FACTORY/REGION | 來自 V_PROC_VARIABLES_PIVOTED |
| PROC_DEF_NAME | 流程定義名稱 |
| DEPT_NAME | 員工部門 |

**TASK_STATUS 判斷邏輯**：
- CANCELLED: DELETE_REASON 不為空
- TODO: 沒有 ASSIGNEE 且沒有 END_TIME
- DOING: 有 ASSIGNEE 且沒有 END_TIME
- DONE_AUTO: 有 ASSIGNEE、沒有 CLAIM_TIME、有 END_TIME
- DONE: 有 END_TIME (其他情況)

### V_HI_PROCINST_NODE
流程實例層，含階層/狀態

| 欄位 | 說明 |
|------|------|
| PROC_INST_ID | 流程實例 ID |
| PROC_STATE | TERMINATED/DONE/DOING |
| DEPTH | 階層深度 (1=根節點, 2+=子流程) |
| SUPER_ID | 父流程 ID |
| DURATION_SEC | 流程總歷時 |
| PLANT/FACTORY/REGION | 來自 V_PROC_VARIABLES_PIVOTED |
| PROC_DEF_NAME | 流程定義名稱 |

### V_HI_BIZ_EVENT_INFO
業務事件層，聚合統計

| 欄位 | 說明 |
|------|------|
| BIZ_EVENT_KEY | 業務事件 Key (BUSINESS_KEY) |
| FIRST_START_TIME | 最早開始時間 |
| FINAL_END_TIME | 最終結束時間 |
| TOTAL_DURATION_SEC | 業務事件總歷時 |
| TASK_TODO_CNT | TODO 任務數 |
| TASK_DOING_CNT | DOING 任務數 |
| TASK_DONE_CNT | DONE 任務數 |
| TASK_AUTOCOMPLETE_CNT | DONE_AUTO 任務數 |
| TASK_CANCELLED_CNT | CANCELLED 任務數 |
| FIRST_PROC_DEF_NAME | 根流程定義名稱 |

---

## SQL 執行順序

| 順序 | 檔案 | 用途 |
|------|------|------|
| 1 | `sql/01_create_database.sql` | 建立 bronze database |
| 2 | `sql/02_create_bpm_tables.sql` | 建立 BPM 相關表 |
| 3 | `sql/03_create_common_tables.sql` | 建立 Common 相關表 |
| 4 | `sql/04_create_silver_database.py` | 建立 silver database |
| 5 | `sql/05_create_silver_views.sql` | 建立 4 個 Silver View |
