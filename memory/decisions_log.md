# Decisions Log

## 用途
記錄已做的技術決策與原因，避免重複討論。

## 何時更新
- 做出技術選擇時
- 改變先前決策時

## ❌ 不該寫的內容
- 待討論的選項
- 未來可能的改進
- 比較分析

---

## 決策紀錄

### 2024-12-12: 同步方案選擇

**決策**：使用 ClickHouse JDBC Bridge

**原因**：
- ClickHouse 原生支援
- 不需要額外 Python 程式
- 官方推薦方案

**放棄選項**：
- Python pyodbc（需自行維護程式）
- ODBC Table Function（Linux ODBC 設定複雜）

---

### 2024-12-12: Table Engine 選擇

**決策**：
- 歷史表使用 ReplacingMergeTree
- 設定表使用 MergeTree

**原因**：
- ReplacingMergeTree 可處理重複資料
- 增量同步時自動去重

---

### 2024-12-12: 同步策略

**決策**：
- 大表（ACT_HI_*, FlowableTaskStats）：Incremental Load
- 小表（設定表）：Full Load

**原因**：
- 大表全量同步耗時
- 小表全量同步簡單可靠

---

### 2025-12-12: JDBC Bridge Datasource 設定修正

**決策**：移除 datasource 設定檔中的 `driverClassName` 屬性

**原因**：
- ClickHouse JDBC Bridge 2.1.0 不支援 `driverClassName` 屬性
- JDBC Driver 會自動從 `driverUrls` 指定的 JAR 檔載入
- 移除後可避免 "Failed to set property driverClassName" 錯誤

**修改檔案**：
- docker/jdbc-bridge/config/datasources/mssql_bpm.json
- docker/jdbc-bridge/config/datasources/mssql_common.json
