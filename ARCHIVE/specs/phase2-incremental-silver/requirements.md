# Requirements Document

## Introduction

本文件定義 DMP Flowable 資料同步專案第二階段的需求，包含增量同步（Incremental Load）、Silver 層資料轉換、以及監控機制。第一階段已完成 Bronze 層全量同步（16 張表，2,134,433 筆），第二階段將提升同步效率並建立資料轉換層。

## Glossary

- **Bronze Layer**：原始資料層，保留 MSSQL 原始結構
- **Silver Layer**：清洗轉換層，進行資料標準化與關聯
- **Incremental Load**：增量同步，僅同步新增或變更的資料
- **Watermark**：水位標記，記錄上次同步的時間點
- **JDBC Bridge**：ClickHouse 透過 JDBC 連接外部資料庫的元件
- **Airbyte**：開源資料整合平台，提供 UI 管理與增量同步

## Requirements

### Requirement 1

**User Story:** As a 資料工程師, I want to 只同步新增或變更的資料, so that 降低同步時間與來源系統負擔。

#### Acceptance Criteria

1. WHEN 執行增量同步 THEN the Sync_System SHALL 僅擷取 watermark 時間之後的資料
2. WHEN 增量同步完成 THEN the Sync_System SHALL 更新 watermark 至最新同步時間
3. WHEN 來源表無時間戳欄位 THEN the Sync_System SHALL 使用全量同步作為 fallback
4. WHEN 增量同步失敗 THEN the Sync_System SHALL 記錄錯誤並保留上次 watermark

### Requirement 2

**User Story:** As a 資料工程師, I want to 建立 Silver 層資料表, so that 提供清洗後的資料供下游分析使用。

#### Acceptance Criteria

1. WHEN Bronze 資料更新 THEN the Transform_System SHALL 自動觸發 Silver 層轉換
2. WHEN 轉換 Silver 層 THEN the Transform_System SHALL 標準化欄位命名（snake_case）
3. WHEN 轉換 Silver 層 THEN the Transform_System SHALL 處理 NULL 值與資料型別轉換
4. WHEN 轉換 Silver 層 THEN the Transform_System SHALL 建立跨表關聯（員工-流程-任務）

### Requirement 3

**User Story:** As a 資料工程師, I want to 監控同步狀態, so that 及時發現並處理同步異常。

#### Acceptance Criteria

1. WHEN 同步執行 THEN the Monitor_System SHALL 記錄開始時間、結束時間、筆數
2. WHEN 同步失敗 THEN the Monitor_System SHALL 記錄錯誤訊息與失敗表名
3. WHEN 查詢同步狀態 THEN the Monitor_System SHALL 提供最近 N 次同步紀錄
4. WHEN 資料筆數差異超過閾值 THEN the Monitor_System SHALL 標記為異常

### Requirement 4

**User Story:** As a 資料工程師, I want to 排程自動執行同步, so that 資料能定期更新而無需手動觸發。

#### Acceptance Criteria

1. WHEN 到達排程時間 THEN the Scheduler SHALL 自動執行增量同步
2. WHEN 排程執行 THEN the Scheduler SHALL 依表優先順序執行（大表優先）
3. WHEN 前次同步未完成 THEN the Scheduler SHALL 跳過本次執行並記錄警告

### Requirement 5

**User Story:** As a 資料工程師, I want to 支援混合式同步策略, so that 依表特性選擇最適方案。

#### Acceptance Criteria

1. WHEN 同步大表（ACT_HI_*, FlowableTaskStats） THEN the Sync_System SHALL 使用增量同步
2. WHEN 同步小表（設定表、對應表） THEN the Sync_System SHALL 使用全量同步
3. WHEN 設定同步策略 THEN the Sync_System SHALL 支援 per-table 設定

