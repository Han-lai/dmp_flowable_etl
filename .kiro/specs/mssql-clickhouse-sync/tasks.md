# Implementation Plan

## Phase 1: JDBC Bridge 環境建置

- [x] 1. 部署 ClickHouse JDBC Bridge



  - [x] 1.1 建立 JDBC Bridge Docker 設定

    - 建立 docker-compose.yml 包含 jdbc-bridge 服務
    - 下載 MSSQL JDBC Driver (mssql-jdbc-12.4.2.jre11.jar)
    - 建立 config 目錄結構
    - _Requirements: 1.1, 3.1_



  - [x] 1.2 設定 MSSQL 資料源連線

    - 建立 datasources/mssql_bpm.json（APP_SRV_BPM 連線）
    - 建立 datasources/mssql_common.json（APP_SRV_COMMON 連線）
    - 測試 JDBC Bridge 啟動與連線
    - _Requirements: 1.1, 1.2_

  - [x] 1.3 驗證 JDBC Bridge 連線

    - 從 ClickHouse 執行 `SELECT * FROM jdbc('mssql_bpm', 'SELECT 1')` 測試連線
    - 驗證可查詢 APP_SRV_BPM 的 ACT_HI_PROCINST 表
    - 驗證可查詢 APP_SRV_COMMON 的 HR_Employee 表
    - _Requirements: 1.1, 1.2, 1.3_





## Phase 2: Bronze 層資料表建立

- [x] 2. 建立 ClickHouse Bronze Database 與資料表


  - [x] 2.1 建立 Bronze Database
    - 執行 `CREATE DATABASE bronze`（Docker 啟動時自動建立）
    - 建立同步狀態追蹤表 `bronze._sync_log`
    - _Requirements: 3.2_

  - [x] 2.2 建立 Flowable 相關 Bronze 表（APP_SRV_BPM）


    - 建立 `bronze.bpm_act_hi_procinst`（流程實例歷史）
    - 建立 `bronze.bpm_act_hi_taskinst`（任務實例歷史）
    - 建立 `bronze.bpm_act_hi_identitylink`（任務參與者歷史）
    - 建立 `bronze.bpm_act_hi_varinst`（流程變數歷史）
    - 建立 `bronze.bpm_act_re_procdef`（流程定義）
    - _Requirements: 1.1, 3.2_

  - [ ] 2.3 建立 DMP 相關 Bronze 表（APP_SRV_COMMON）
    - 建立 `bronze.common_flowable_task_stats`（任務統計彙總）
    - 建立 `bronze.common_hr_employee`（員工主檔）
    - 建立 `bronze.common_process_role_user_mapping`（角色-員工對應）
    - 建立 `bronze.common_process_role_group`（角色群組定義）
    - 建立 `bronze.common_process_role_group_mapping`（角色群組對應）




    - 建立 `bronze.common_emp_node_role_mapping`（員工-節點角色）
    - 建立 `bronze.common_emp_org_info_mapping`（員工-組織對應）
    - 建立 `bronze.common_emp_user_group_mapping`（員工-群組對應）
    - 建立 `bronze.common_user_group`（使用者群組定義）

    - 建立 `bronze.common_dmp_function_config`（功能設定）
    - 建立 `bronze.common_dmp_function_client_mapping`（客戶端對應）
    - _Requirements: 1.2, 3.2_





## Phase 3: 資料同步實作

- [ ] 3. 實作 Full Load 同步
  - [x] 3.1 建立 Full Load 同步 SQL 腳本




    - 建立 `sync/full_load_bpm.sql`（Flowable 表全量同步）
    - 建立 `sync/full_load_common.sql`（DMP 表全量同步）
    - 每個 INSERT 語句包含 _sync_time, _source_db, _batch_id
    - _Requirements: 3.1_



  - [ ] 3.2 執行首次全量同步
    - 執行 Flowable 表全量同步（5 張表）
    - 執行 DMP 表全量同步（11 張表）
    - 記錄同步結果到 `bronze._sync_log`

    - _Requirements: 3.1, 4.1_

- [ ] 4. 實作 Incremental Load 同步
  - [ ] 4.1 建立 Incremental Load 同步 SQL 腳本
    - 建立 `sync/incremental_load.sql`（增量同步模板）




    - 使用時間戳欄位（LAST_UPDATED_TIME_, SyncTime 等）作為增量條件

    - _Requirements: 3.1_



## Phase 4: 資料驗證

- [ ] 5. 資料完整性驗證
  - [ ] 5.1 建立 Row Count 比對查詢
    - 建立 `validation/row_count_check.sql`
    - 比對 MSSQL 與 ClickHouse 的 row count
    - 差異應 < 0.1%
    - _Requirements: 4.1_

  - [ ] 5.2 建立資料品質檢查查詢
    - 建立 `validation/data_quality_check.sql`
    - 檢查 Primary Key 唯一性
    - 檢查非空欄位
    - 檢查時間欄位範圍
    - _Requirements: 4.1_

  - [ ] 5.3 執行驗證並產出報告
    - 執行所有驗證查詢
    - 產出驗證報告（CSV 或 Markdown）
    - _Requirements: 4.1, 4.3_

## Phase 5: 文件與交付

- [ ] 6. 完成第一階段交付文件
  - [ ] 6.1 更新資料表關聯文件
    - 確認 Join Key 正確性
    - 補充實際資料範例
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 6.2 建立操作手冊
    - JDBC Bridge 啟動/停止指令
    - 同步執行指令
    - 常見問題排除
    - _Requirements: 4.2_
