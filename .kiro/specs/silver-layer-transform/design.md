# Silver Layer Transform Design Document

## Overview

本設計文件定義 Silver Layer 的資料轉換架構，將 Bronze 層原始資料轉換為「可計算指標」的中介資料表。Silver Layer 保留事件與事實粒度，不進行聚合計算。

---

## Metric 對應分析（18 個指標）

以下表格說明 metric_cal.md 中 18 個指標與現有 Bronze 表的對應關係：

| # | 指標名稱 | 關鍵欄位 | Bronze 來源表 | 支援狀態 | Silver 表 | 備註 |
|---|----------|----------|---------------|----------|-----------|------|
| 1 | 業務事件總歷時 | BUSINESS_KEY_, START_TIME_, END_TIME_ | bpm_act_hi_procinst | ✅ 完全支援 | fact_biz_event | GROUP BY BUSINESS_KEY_ |
| 2 | 流程執行總時間 | BUSINESS_KEY_, DURATION_ | bpm_act_hi_procinst | ✅ 完全支援 | fact_biz_event | SUM(DURATION_) |
| 3 | 任務處理總時間 | CLAIM_TIME_, END_TIME_ | bpm_act_hi_taskinst | ✅ 完全支援 | fact_task_instance | work_duration_seconds |
| 4 | 流程總歷時 | START_TIME_, END_TIME_, DURATION_ | bpm_act_hi_procinst | ✅ 完全支援 | fact_process_instance | duration_seconds |
| 5 | 任務閒置時長 | START_TIME_, CLAIM_TIME_ | bpm_act_hi_taskinst | ✅ 完全支援 | fact_task_instance | idle_duration_seconds |
| 6 | 個人處理時長 | CLAIM_TIME_, END_TIME_ | bpm_act_hi_taskinst | ✅ 完全支援 | fact_task_instance | work_duration_seconds |
| 7 | 任務總歷時 | START_TIME_, END_TIME_, DURATION_ | bpm_act_hi_taskinst | ✅ 完全支援 | fact_task_instance | total_duration_seconds |
| 8 | 在途業務事件總數 | FIRST_START_TIME, FINAL_END_TIME | bpm_act_hi_procinst | ✅ 完全支援 | fact_biz_event | is_in_progress = 1 |
| 9 | 在途任務總數 | NODE_STATE (TODO/DOING) | bpm_act_hi_taskinst | ✅ 完全支援 | fact_task_instance | task_status IN ('TODO','DOING') |
| 10 | 逾期在途業務事件數 | FIRST_START_TIME, HealthSettings | bpm_act_hi_procinst + ❌ HealthSettings | ⚠️ 部分支援 | fact_biz_event | **缺少 HealthSettings 表** |
| 11 | 平均業務事件總歷時 | FIRST_START_TIME, FINAL_END_TIME | bpm_act_hi_procinst | ✅ 完全支援 | fact_biz_event | AVG(total_duration_seconds) |
| 12 | 平均任務處理時長 | CLAIM_TIME_, END_TIME_ | bpm_act_hi_taskinst | ✅ 完全支援 | fact_task_instance | AVG(work_duration_seconds) |
| 13 | 事件自動完成率 | DELETE_REASON_ (auto) | bpm_act_hi_taskinst | ✅ 完全支援 | fact_task_instance | task_status = 'AUTOCOMPLETE' |
| 14 | 在途任務數-依部門 | ASSIGNEE_, DeptCodeLname | bpm_act_hi_taskinst + common_hr_employee | ✅ 完全支援 | fact_task_instance + dim_employee | JOIN department_name |
| 15 | 在途任務數-依地區 | Factory, AreaLname | common_flowable_task_stats + common_hr_employee | ✅ 完全支援 | fact_task_stats + dim_employee | 用 Factory + area_name 替代 |
| 16 | 在途任務數-依廠區 | Plant | common_flowable_task_stats | ✅ 完全支援 | fact_task_stats | plant 欄位 |
| 17 | 在途任務數-依人員 | ASSIGNEE_, EmpName | bpm_act_hi_taskinst + common_hr_employee | ✅ 完全支援 | fact_task_instance + dim_employee | JOIN emp_name |
| 18 | 在途流程健康度快照 | DMP_NAME, PROC_PLANT, PROC_FACTORY | bpm_act_hi_procinst + bpm_act_hi_varinst | ⚠️ 部分支援 | fact_biz_event | **需從 varinst 取 DMP_NAME** |

### 支援狀態統計

| 狀態 | 數量 | 說明 |
|------|------|------|
| ✅ 完全支援 | 16 個 | Bronze 表有完整欄位，Silver 層可直接計算 |
| ⚠️ 部分支援 | 2 個 | 缺少維度表或需額外處理 |

### 缺口說明

| 缺少項目 | 影響指標 | 替代方案 |
|----------|----------|----------|
| HealthSettings 表 | #10 逾期在途業務事件數 | 需另外建立設定表，或硬編碼紅燈天數 |
| DMP_NAME 變數 | #18 在途流程健康度快照 | 從 ACT_HI_VARINST 取得 NAME_='dmpName' 的 TEXT_ 值 |

---

### 設計原則

1. **保留原始粒度**：不做聚合，保留每筆事件/任務的明細
2. **標準化命名**：統一欄位命名規則（snake_case）
3. **型別轉換**：時間統一為秒、狀態統一為標準碼
4. **派生欄位**：計算 duration、status、is_xxx 等中間欄位
5. **可追溯性**：保留原始主鍵與來源標記

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Bronze Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  bpm_act_hi_procinst    │  bpm_act_hi_taskinst                  │
│  bpm_act_hi_varinst     │  bpm_act_hi_identitylink              │
│  bpm_act_re_procdef     │  common_flowable_task_stats           │
│  common_hr_employee     │  common_process_role_user_mapping     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ Transform (Materialized View / INSERT SELECT)
┌─────────────────────────────────────────────────────────────────┐
│                        Silver Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  fact_biz_event         │  業務事件粒度（by BUSINESS_KEY_）      │
│  fact_process_instance  │  流程實例粒度（by PROC_INST_ID_）      │
│  fact_task_instance     │  任務實例粒度（by TASK_ID_）           │
│  fact_task_stats        │  任務統計（by TaskId）                 │
│  dim_employee           │  員工維度（by EmpCode）                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (Future: Gold Layer)
┌─────────────────────────────────────────────────────────────────┐
│                        Gold Layer (未來)                         │
│  KPI 聚合、Dashboard 資料                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components and Interfaces

### 轉換方式選擇

| 方式 | 優點 | 缺點 | 適用場景 |
|------|------|------|----------|
| Materialized View | 自動更新、維護簡單 | 效能受限、複雜 JOIN 困難 | 簡單轉換 |
| INSERT SELECT | 完全控制、效能好 | 需手動觸發 | 複雜轉換 |
| Python ETL | 彈性高、可加邏輯 | 需維護程式 | 特殊處理 |

**決策**：採用 INSERT SELECT + Python 排程，因為：
- 需要跨表 JOIN（Bronze 表之間）
- 需要複雜的派生欄位計算
- 需要控制更新頻率

---

## Data Models

### 1. silver.fact_biz_event（業務事件表）

| 欄位名稱 | 型別 | 來源 | 說明 | 支援 Metric |
|----------|------|------|------|-------------|
| biz_event_key | String | BUSINESS_KEY_ | 業務事件主鍵 | - |
| first_start_time | DateTime | MIN(START_TIME_) | 首個流程開始時間 | 在途事件數、逾期數 |
| final_end_time | Nullable(DateTime) | MAX(END_TIME_) | 最後流程結束時間 | 在途事件數 |
| total_duration_seconds | Nullable(Int64) | 派生 | 總歷時（秒） | 平均業務事件總歷時 |
| process_count | Int32 | COUNT(*) | 流程實例數量 | - |
| is_in_progress | UInt8 | 派生 | 是否在途 | 在途事件數 |
| first_proc_def_key | String | 首個流程 | 首個流程定義 Key | 流程健康度快照 |
| first_proc_def_name | String | 首個流程 | 首個流程名稱 | 流程健康度快照 |
| _transform_time | DateTime64(3) | 系統 | 轉換時間 | - |

**派生邏輯：**
- `total_duration_seconds` = `dateDiff('second', first_start_time, final_end_time)`
- `is_in_progress` = `final_end_time IS NULL ? 1 : 0`

---

### 2. silver.fact_process_instance（流程實例表）

| 欄位名稱 | 型別 | 來源 | 說明 | 支援 Metric |
|----------|------|------|------|-------------|
| proc_inst_id | String | PROC_INST_ID_ | 流程實例 ID | - |
| biz_event_key | String | BUSINESS_KEY_ | 業務事件 Key | JOIN 用 |
| proc_def_id | String | PROC_DEF_ID_ | 流程定義 ID | - |
| proc_def_key | String | JOIN | 流程定義 Key | - |
| proc_def_name | String | JOIN | 流程名稱 | - |
| start_time | DateTime | START_TIME_ | 開始時間 | - |
| end_time | Nullable(DateTime) | END_TIME_ | 結束時間 | - |
| duration_seconds | Nullable(Int64) | DURATION_ / 1000 | 執行時長（秒） | 流程執行總時間 |
| start_user_id | Nullable(String) | START_USER_ID_ | 啟動人員 | - |
| is_completed | UInt8 | 派生 | 是否完成 | - |
| delete_reason | Nullable(String) | DELETE_REASON_ | 刪除原因 | - |
| _transform_time | DateTime64(3) | 系統 | 轉換時間 | - |

**派生邏輯：**
- `duration_seconds` = `DURATION_ / 1000`（原始為毫秒）
- `is_completed` = `END_TIME_ IS NOT NULL ? 1 : 0`

---

### 3. silver.fact_task_instance（任務實例表）

| 欄位名稱 | 型別 | 來源 | 說明 | 支援 Metric |
|----------|------|------|------|-------------|
| task_id | String | ID_ | 任務 ID | - |
| proc_inst_id | String | PROC_INST_ID_ | 流程實例 ID | JOIN 用 |
| task_def_key | Nullable(String) | TASK_DEF_KEY_ | 任務定義 Key | - |
| task_name | Nullable(String) | NAME_ | 任務名稱 | - |
| assignee_emp_code | Nullable(String) | ASSIGNEE_ | 承接人工號 | 在途任務數-依人員 |
| start_time | DateTime | START_TIME_ | 建立時間 | - |
| claim_time | Nullable(DateTime) | CLAIM_TIME_ | 認領時間 | - |
| end_time | Nullable(DateTime) | END_TIME_ | 完成時間 | - |
| idle_duration_seconds | Nullable(Int64) | 派生 | 閒置時長（秒） | 任務閒置時長 |
| work_duration_seconds | Nullable(Int64) | 派生 | 處理時長（秒） | 個人處理時長、平均任務處理時長 |
| total_duration_seconds | Nullable(Int64) | 派生 | 總歷時（秒） | 任務總歷時 |
| task_status | LowCardinality(String) | 派生 | 任務狀態 | 在途任務數 |
| delete_reason | Nullable(String) | DELETE_REASON_ | 刪除原因 | - |
| _transform_time | DateTime64(3) | 系統 | 轉換時間 | - |

**派生邏輯：**
- `idle_duration_seconds` = `dateDiff('second', start_time, claim_time)`
- `work_duration_seconds` = `dateDiff('second', claim_time, end_time)`
- `total_duration_seconds` = `dateDiff('second', start_time, end_time)`
- `task_status` = 
  - `'CANCELLED'` if DELETE_REASON_ IS NOT NULL
  - `'DONE'` if END_TIME_ IS NOT NULL AND DELETE_REASON_ LIKE '%auto%'
  - `'AUTOCOMPLETE'` if END_TIME_ IS NOT NULL AND DELETE_REASON_ LIKE '%auto%'
  - `'DOING'` if CLAIM_TIME_ IS NOT NULL AND END_TIME_ IS NULL
  - `'TODO'` otherwise

---

### 4. silver.fact_task_stats（任務統計表）

| 欄位名稱 | 型別 | 來源 | 說明 | 支援 Metric |
|----------|------|------|------|-------------|
| task_id | String | TaskId | 任務 ID | - |
| proc_inst_id | Nullable(String) | ProcessInstanceId | 流程實例 ID | - |
| proc_def_key | Nullable(String) | ProcessDefinitionKey | 流程定義 Key | - |
| proc_def_name | Nullable(String) | ProcessDefinitionName | 流程名稱 | - |
| plant | Nullable(String) | Plant | 廠區 | 在途任務數-依廠區 |
| factory | Nullable(String) | Factory | 工廠 | 在途任務數-依地區 |
| production_area | Nullable(String) | ProductionArea | 生產區域 | - |
| task_name | Nullable(String) | TaskName | 任務名稱 | - |
| task_status | LowCardinality(String) | TaskStatus | 任務狀態（標準化） | 在途任務數 |
| assignee_emp_code | Nullable(String) | TaskAssignee | 承接人工號 | 在途任務數-依人員 |
| assignee_name | Nullable(String) | TaskAssigneeName | 承接人姓名 | - |
| task_create_time | Nullable(DateTime) | TaskCreateTime | 建立時間 | - |
| task_claim_time | Nullable(DateTime) | TaskClaimTime | 認領時間 | - |
| task_end_time | Nullable(DateTime) | TaskEndTime | 完成時間 | - |
| task_duration_seconds | Nullable(Int64) | 派生 | 總歷時（秒） | 任務總歷時 |
| task_work_seconds | Nullable(Int64) | 派生 | 處理時長（秒） | 個人處理時長 |
| task_create_date | Nullable(Date) | TaskCreateDate | 建立日期 | 分區用 |
| _transform_time | DateTime64(3) | 系統 | 轉換時間 | - |

**派生邏輯：**
- `task_duration_seconds` = `TaskDurationMinutes * 60`
- `task_work_seconds` = `TaskWorkMinutes * 60`
- `task_status` = 標準化（TODO/DOING/DONE/AUTOCOMPLETE）

---

### 5. silver.dim_employee（員工維度表）

| 欄位名稱 | 型別 | 來源 | 說明 | 支援 Metric |
|----------|------|------|------|-------------|
| emp_code | String | EmpCode | 員工工號（主鍵） | JOIN 用 |
| emp_name | Nullable(String) | EmpName | 員工姓名 | 在途任務數-依人員 |
| display_name | Nullable(String) | DisplayName | 顯示名稱 | - |
| ad_account | Nullable(String) | ADAccount | AD 帳號 | - |
| email | Nullable(String) | Email | 電子郵件 | - |
| department_code | Nullable(String) | DeptCode | 部門代碼 | - |
| department_name | Nullable(String) | DeptCodeLname | 部門名稱 | 在途任務數-依部門 |
| factory_code | Nullable(String) | FactoryCode | 工廠代碼 | - |
| factory_name | Nullable(String) | FactoryLname | 工廠名稱 | - |
| area_id | Nullable(String) | AreaID | 地區 ID | - |
| area_name | Nullable(String) | AreaLname | 地區名稱 | 在途任務數-依地區 |
| supervisor_emp_code | Nullable(String) | Supervisor | 主管工號 | - |
| is_active | UInt8 | 派生 | 是否在職 | - |
| terminate_date | Nullable(DateTime) | TerminateDate | 離職日期 | - |
| _transform_time | DateTime64(3) | 系統 | 轉換時間 | - |

**派生邏輯：**
- `is_active` = `TerminateDate IS NULL OR TerminateDate > now() ? 1 : 0`

---


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: 業務事件分群正確性
*For any* 一組具有相同 BUSINESS_KEY_ 的流程實例，轉換後的 fact_biz_event 記錄的 first_start_time 應等於所有流程實例中 START_TIME_ 的最小值，final_end_time 應等於所有流程實例中 END_TIME_ 的最大值。
**Validates: Requirements 1.2**

### Property 2: 在途狀態標記正確性
*For any* fact_biz_event 記錄，若 final_end_time 為 NULL，則 is_in_progress 應為 1；否則應為 0。
**Validates: Requirements 1.3**

### Property 3: 業務事件總歷時計算正確性
*For any* 已完成的 fact_biz_event 記錄（final_end_time IS NOT NULL），total_duration_seconds 應等於 final_end_time 與 first_start_time 之間的秒數差。
**Validates: Requirements 1.4**

### Property 4: 流程實例時長單位轉換正確性
*For any* fact_process_instance 記錄，duration_seconds 應等於原始 DURATION_ 除以 1000（毫秒轉秒）。
**Validates: Requirements 2.2**

### Property 5: 流程定義 JOIN 正確性
*For any* fact_process_instance 記錄，proc_def_name 應與對應 ACT_RE_PROCDEF 的 NAME_ 欄位相同。
**Validates: Requirements 2.3**

### Property 6: 任務閒置時長計算正確性
*For any* fact_task_instance 記錄，若 claim_time 不為 NULL，則 idle_duration_seconds 應等於 claim_time 與 start_time 之間的秒數差。
**Validates: Requirements 3.2**

### Property 7: 任務處理時長計算正確性
*For any* fact_task_instance 記錄，若 claim_time 與 end_time 皆不為 NULL，則 work_duration_seconds 應等於 end_time 與 claim_time 之間的秒數差。
**Validates: Requirements 3.3**

### Property 8: 任務狀態派生正確性
*For any* fact_task_instance 記錄，task_status 應根據以下規則派生：
- DELETE_REASON_ 不為 NULL → 'CANCELLED'
- END_TIME_ 不為 NULL 且 DELETE_REASON_ 包含 'auto' → 'AUTOCOMPLETE'
- END_TIME_ 不為 NULL → 'DONE'
- CLAIM_TIME_ 不為 NULL 且 END_TIME_ 為 NULL → 'DOING'
- 其他 → 'TODO'
**Validates: Requirements 3.5**

### Property 9: 任務統計時長單位轉換正確性
*For any* fact_task_stats 記錄，task_duration_seconds 應等於 TaskDurationMinutes * 60，task_work_seconds 應等於 TaskWorkMinutes * 60。
**Validates: Requirements 4.2, 4.3**

### Property 10: 員工在職狀態計算正確性
*For any* dim_employee 記錄，若 terminate_date 為 NULL 或大於當前時間，則 is_active 應為 1；否則應為 0。
**Validates: Requirements 5.2**

---

## Error Handling

| 錯誤類型 | 處理方式 |
|----------|----------|
| NULL 時間欄位 | 派生欄位設為 NULL，不拋錯 |
| 無效的 BUSINESS_KEY_ | 跳過該記錄，記錄到錯誤日誌 |
| JOIN 失敗（找不到對應記錄） | 使用 LEFT JOIN，保留原始記錄 |
| 型別轉換失敗 | 設為 NULL，記錄到錯誤日誌 |

---

## Testing Strategy

### 單元測試
- 測試各派生欄位的計算邏輯
- 測試狀態標準化邏輯
- 測試 NULL 值處理

### Property-Based Testing
使用 Hypothesis（Python）進行屬性測試：
- 生成隨機的 Bronze 資料
- 執行轉換邏輯
- 驗證 Correctness Properties

### 整合測試
- 驗證 Bronze → Silver 完整流程
- 驗證資料筆數一致性
- 驗證主鍵唯一性

---

## Bronze → Silver 銜接說明

### 轉換觸發方式
- 排程執行（每日/每小時）
- 手動觸發

### 轉換順序
1. `dim_employee`（維度表優先）
2. `fact_process_instance`（需要 JOIN 流程定義）
3. `fact_biz_event`（需要 GROUP BY 流程實例）
4. `fact_task_instance`
5. `fact_task_stats`

### 增量更新策略
- 使用 `_sync_time` 作為增量條件
- 每次轉換只處理新增/更新的 Bronze 資料
- Silver 表使用 ReplacingMergeTree 處理重複

