# Requirements Document

## Introduction

本文件定義 Silver Layer 資料轉換的需求規格。Silver Layer 負責對 Bronze 層原始資料進行清洗、標準化與結構整理，建立「可計算指標（Metric-ready）」的中介資料表，但不直接產生最終 KPI（那是 Gold 層的責任）。

## Glossary

- **Silver Layer**：資料倉儲中介層，負責資料清洗與標準化
- **Bronze Layer**：原始資料層，保留來源系統原始結構
- **派生欄位（Derived Column）**：基於原始欄位計算產生的新欄位
- **業務事件（Biz Event）**：由一或多個流程實例組成的完整業務流程
- **流程實例（Process Instance）**：Flowable 中的單一流程執行記錄
- **任務實例（Task Instance）**：流程中的單一人工任務
- **在途（In-Progress）**：尚未完成的事件/任務
- **閒置時長（Idle Duration）**：任務建立到認領之間的等待時間
- **處理時長（Work Duration）**：任務認領到完成之間的處理時間

---

## Requirements

### Requirement 1: 業務事件 Silver 表

**User Story:** As a 資料分析師, I want 業務事件層級的清洗資料, so that 我可以計算業務事件相關指標（在途數、總歷時、逾期數）。

#### Acceptance Criteria

1. WHEN Bronze 層 ACT_HI_PROCINST 資料更新 THEN Silver Layer SHALL 產生 silver.fact_biz_event 表，包含業務事件粒度的彙總資料
2. WHEN 業務事件包含多個流程實例 THEN Silver Layer SHALL 以 BUSINESS_KEY_ 分群，計算 first_start_time 與 final_end_time
3. WHEN 業務事件尚未完成（final_end_time IS NULL）THEN Silver Layer SHALL 標記 is_in_progress = true
4. WHEN 業務事件已完成 THEN Silver Layer SHALL 計算 total_duration_seconds 派生欄位
5. WHEN 業務事件資料轉換完成 THEN Silver Layer SHALL 保留原始 BUSINESS_KEY_ 作為主鍵

### Requirement 2: 流程實例 Silver 表

**User Story:** As a 資料分析師, I want 流程實例層級的清洗資料, so that 我可以計算流程執行時間與狀態。

#### Acceptance Criteria

1. WHEN Bronze 層 ACT_HI_PROCINST 資料更新 THEN Silver Layer SHALL 產生 silver.fact_process_instance 表
2. WHEN 流程實例有 DURATION_ 欄位 THEN Silver Layer SHALL 轉換為 duration_seconds（秒）
3. WHEN 流程實例關聯流程定義 THEN Silver Layer SHALL JOIN ACT_RE_PROCDEF 取得 process_name 與 process_key
4. WHEN 流程實例資料轉換完成 THEN Silver Layer SHALL 計算 is_completed 布林欄位

### Requirement 3: 任務實例 Silver 表

**User Story:** As a 資料分析師, I want 任務實例層級的清洗資料, so that 我可以計算任務處理時長、閒置時長與任務狀態分布。

#### Acceptance Criteria

1. WHEN Bronze 層 ACT_HI_TASKINST 資料更新 THEN Silver Layer SHALL 產生 silver.fact_task_instance 表
2. WHEN 任務有 START_TIME_ 與 CLAIM_TIME_ THEN Silver Layer SHALL 計算 idle_duration_seconds（閒置時長）
3. WHEN 任務有 CLAIM_TIME_ 與 END_TIME_ THEN Silver Layer SHALL 計算 work_duration_seconds（處理時長）
4. WHEN 任務有 START_TIME_ 與 END_TIME_ THEN Silver Layer SHALL 計算 total_duration_seconds（總歷時）
5. WHEN 任務有 DELETE_REASON_ THEN Silver Layer SHALL 派生 task_status 欄位（TODO/DOING/DONE/AUTOCOMPLETE/CANCELLED）
6. WHEN 任務有 ASSIGNEE_ THEN Silver Layer SHALL 保留並標準化為 assignee_emp_code

### Requirement 4: 任務統計 Silver 表

**User Story:** As a 資料分析師, I want 任務統計的清洗資料, so that 我可以快速查詢任務分布與效率指標。

#### Acceptance Criteria

1. WHEN Bronze 層 FlowableTaskStats 資料更新 THEN Silver Layer SHALL 產生 silver.fact_task_stats 表
2. WHEN 任務統計有 TaskDurationMinutes THEN Silver Layer SHALL 轉換為 task_duration_seconds
3. WHEN 任務統計有 TaskWorkMinutes THEN Silver Layer SHALL 轉換為 task_work_seconds
4. WHEN 任務統計有 TaskStatus THEN Silver Layer SHALL 標準化狀態碼（TODO/DOING/DONE/AUTOCOMPLETE）
5. WHEN 任務統計有地理欄位（Plant/Factory/ProductionArea）THEN Silver Layer SHALL 保留並標準化命名

### Requirement 5: 員工維度 Silver 表

**User Story:** As a 資料分析師, I want 員工維度的清洗資料, so that 我可以關聯任務承接人與組織資訊。

#### Acceptance Criteria

1. WHEN Bronze 層 HR_Employee 資料更新 THEN Silver Layer SHALL 產生 silver.dim_employee 表
2. WHEN 員工有 TerminateDate THEN Silver Layer SHALL 計算 is_active 布林欄位
3. WHEN 員工有組織欄位 THEN Silver Layer SHALL 標準化為 department_name、factory_name、area_name
4. WHEN 員工資料轉換完成 THEN Silver Layer SHALL 以 emp_code 作為主鍵

