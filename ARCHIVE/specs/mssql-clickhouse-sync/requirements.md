# Requirements Document

## Introduction

本專案目標是建立 MSSQL 到 ClickHouse 的資料同步架構，採用 Bronze / Silver 分層設計。第一階段聚焦於：
1. 連線 MSSQL 並探索目標資料表結構
2. 設計 Bronze 層（Raw Data 同步）
3. 驗證資料同步的可行性與完整性

### 資料來源

**MSSQL Server:** `twtpesqldv2.delta.corp:1433`

資料庫：
- **APP_SRV_BPM**：Flowable BPM 流程引擎資料（task 定義、執行結果、歷史資料）
- **APP_SRV_COMMON**：Common 資料（員工、組織、ERP 等，作為分析維度）

**連線工具:** Python pyodbc

---

## Requirements

### Requirement 1: MSSQL 資料表探索與分析

**User Story:** As a 資料工程師, I want 連線到 MSSQL 並探索目標資料表的結構與內容, so that 我能了解資料特性並設計適當的同步策略。

#### Acceptance Criteria

1. WHEN 連線到 APP_SRV_BPM 資料庫 THEN 系統 SHALL 能夠查詢以下 Flowable 表的 schema 與 row count：
   - ACT_HI_IDENTITYLINK
   - ACT_HI_PROCINST
   - ACT_HI_TASKINST
   - ACT_HI_VARINST
   - ACT_RE_PROCDEF

2. WHEN 連線到 APP_SRV_COMMON 資料庫 THEN 系統 SHALL 能夠查詢以下 DMP 表的 schema 與 row count：
   - DMPFunctionClientMapping
   - DMPFunctionConfig
   - EmpNodeRoleMapping
   - EmpOrgInfoMapping
   - EmpUserGroupMapping
   - FlowableTaskStats
   - HR_Employee
   - ProcessRoleGroup
   - ProcessRoleGroupMapping
   - ProcessRoleUserMapping
   - UserGroup

3. WHEN 查詢資料表結構 THEN 系統 SHALL 記錄每張表的：
   - 欄位名稱與資料型別
   - Primary Key / Index 資訊
   - 預估資料量（row count）
   - 是否有時間戳欄位（用於增量同步判斷）

---

### Requirement 2: 資料表關聯分析

**User Story:** As a 資料工程師, I want 分析 Flowable 與 DMP 資料表之間的關聯關係, so that 我能設計正確的 join 策略供後續 Silver 層使用。

#### Acceptance Criteria

1. WHEN 分析 Flowable 表 THEN 系統 SHALL 識別出：
   - PROC_INST_ID_ 作為流程實例的主要關聯鍵
   - TASK_ID_ 作為任務的主要關聯鍵
   - USER_ID_ / ASSIGNEE_ 作為人員關聯鍵

2. WHEN 分析 DMP 表 THEN 系統 SHALL 識別出：
   - 員工編號（emp_no / employee_id）作為人員主鍵
   - 組織代碼作為部門關聯鍵
   - 角色/群組 ID 作為權限關聯鍵

3. WHEN 完成關聯分析 THEN 系統 SHALL 產出一份關聯圖譜文件，說明：
   - Flowable 表之間的關聯（process → task → variable）
   - DMP 表如何補充 Flowable 的人員/組織資訊

---

### Requirement 3: MSSQL → ClickHouse 同步方案設計

**User Story:** As a 資料工程師, I want 設計 Batch 同步方案將 MSSQL 資料同步到 ClickHouse Bronze 層, so that 資料能以 Raw Data 形式保留並可追溯。

#### Acceptance Criteria

1. WHEN 設計同步方案 THEN 系統 SHALL 支援以下同步模式：
   - Full Load（全量同步）：適用於小表或設定表
   - Incremental Load（增量同步）：適用於有時間戳的歷史表

2. WHEN 同步資料到 Bronze 層 THEN 系統 SHALL：
   - 保留 MSSQL 原始欄位名稱與結構
   - 新增 `_sync_time` 欄位記錄同步時間
   - 新增 `_source_db` 欄位標記來源資料庫

3. IF 資料表更新頻率不同 THEN 系統 SHALL 支援獨立設定每張表的同步排程

---

### Requirement 4: 第一階段驗收標準

**User Story:** As a 專案負責人, I want 定義明確的驗收標準, so that 我能判斷 MSSQL → ClickHouse 同步是否成功。

#### Acceptance Criteria

1. WHEN 同步完成 THEN 系統 SHALL 驗證：
   - ClickHouse row count = MSSQL row count（允許同步期間的微小差異）
   - 關鍵欄位的資料型別正確轉換
   - 無資料截斷或亂碼

2. WHEN 建立監控機制 THEN 系統 SHALL 提供：
   - 每次同步的 row count 比對報告
   - 同步延遲時間（從 MSSQL 更新到 ClickHouse 可查詢）
   - 同步失敗的告警機制

3. WHEN 完成第一階段 THEN 系統 SHALL 產出：
   - Bronze 層資料表建立完成
   - 至少一次成功的全量同步
   - 資料完整性驗證報告
