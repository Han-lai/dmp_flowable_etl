# Implementation Plan

## Phase 1: JDBC Bridge 環境建置

- [x] 1. 部署 ClickHouse JDBC Bridge

  - [x] 1.1 建立 JDBC Bridge Docker 設定
    - 建立 docker-compose.yml 包含 jdbc-bridge 服務
    - 使用 MSSQL JDBC Driver (mssql-jdbc-7.4.1.jre8.jar)
    - 建立 config 目錄結構
    - _Requirements: 1.1, 3.1_

  - [x] 1.2 設定 MSSQL 資料源連線
    - 建立 datasources/mssql_master.json（連線到 master，可存取 APP_SRV_BPM 和 APP_SRV_COMMON）
    - 建立 datasources/postgres_cleaned_data.json（PostgreSQL 連線）
    - 關鍵設定：需加上 `driverClassName: com.microsoft.sqlserver.jdbc.SQLServerDriver`
    - 測試 JDBC Bridge 啟動與連線
    - _Requirements: 1.1, 1.2_

  - [x] 1.3 驗證 JDBC Bridge 連線
    - 從 ClickHouse 執行 `SELECT * FROM jdbc('mssql_master', 'SELECT 1')` 測試連線
    - 可透過 `APP_SRV_BPM.dbo.表名` 查詢 BPM 資料庫
    - 可透過 `APP_SRV_COMMON.dbo.表名` 查詢 COMMON 資料庫
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

  - [x] 2.3 建立 DMP 相關 Bronze 表（APP_SRV_COMMON）
    - 建立 `bronze.common_flowable_task_stats`（任務統計彙總）- 732,973 筆
    - 建立 `bronze.common_hr_employee`（員工主檔）- 169,907 筆
    - 建立 `bronze.common_process_role_user_mapping`（角色-員工對應）- 12,714 筆
    - 建立 `bronze.common_process_role_group`（角色群組定義）- 19 筆
    - 建立 `bronze.common_process_role_group_mapping`（角色群組對應）- 690 筆
    - 建立 `bronze.common_emp_node_role_mapping`（員工-節點角色）- 2,778 筆
    - 建立 `bronze.common_emp_org_info_mapping`（員工-組織對應）- 1,129 筆
    - 建立 `bronze.common_emp_user_group_mapping`（員工-群組對應）- 1,248 筆
    - 建立 `bronze.common_user_group`（使用者群組定義）- 9 筆
    - 建立 `bronze.common_dmp_function_config`（功能設定）- 185 筆
    - 建立 `bronze.common_dmp_function_client_mapping`（客戶端對應）- 57 筆
    - _Requirements: 1.2, 3.2_





## Phase 3: 資料同步實作

- [x] 3. 實作 Full Load 同步
  - [x] 3.1 建立 Full Load 同步程式
    - 建立 `sync/sync_to_clickhouse.py`（Python 主控同步程式）
    - 使用 `CREATE TABLE AS SELECT` 一步完成建表+同步
    - 使用 `tuple()` ORDER BY 避免 Nullable 欄位問題
    - 同步結果自動輸出到 `logs/` 目錄
    - _Requirements: 3.1_

  - [x] 3.2 執行首次全量同步
    - 執行 Flowable 表全量同步（5 張表）- 1,201,952 筆
    - 執行 DMP 表全量同步（11 張表）- 921,709 筆
    - 總計：16 張表，2,123,661 筆，17.89 秒完成
    - 平均速度：118,700 筆/秒
    - _Requirements: 3.1, 4.1_

- [ ] 4. 實作 Incremental Load 同步（未來需求）
  - [ ] 4.1 建立 Incremental Load 同步程式
    - 使用時間戳欄位（LAST_UPDATED_TIME_, SyncTime 等）作為增量條件
    - _Requirements: 3.1_



## Phase 4: 資料驗證

- [x] 5. 資料完整性驗證
  - [x] 5.1 建立 Row Count 比對程式
    - 建立 `validation/validate_sync.py`
    - 比對 MSSQL 與 ClickHouse 的 row count
    - _Requirements: 4.1_

  - [x] 5.2 執行驗證並產出報告
    - 執行驗證程式
    - 報告輸出到 `logs/validation_report_*.txt`
    - _Requirements: 4.1, 4.3_

## Phase 5: 文件與交付

- [x] 6. 完成第一階段交付文件
  - [x] 6.1 資料表關聯文件
    - `docs/table_relationships.md`
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 6.2 操作手冊
    - `docs/operation_guide.md`
    - _Requirements: 4.2_
