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

### 2024-12-12: MSSQL Mock Schema

**決策**：使用完整 schema（與真實系統一致）

**原因**：
- 方便測試與驗證
- 避免欄位不一致問題

**表數量**：
- APP_SRV_BPM：5 張表（21-28 欄）
- APP_SRV_COMMON：11 張表（4-52 欄）

---

### 2024-12-12: ClickHouse 連線設定

**決策**：手動建立 listen.xml 設定 `0.0.0.0`

**原因**：
- 預設只監聯 localhost
- 需要外部連線存取

---

### 2024-12-17: JDBC Bridge MSSQL 連線成功

**決策**：使用單一 `mssql_master` datasource 連線到 master database

**原因**：
- 可透過 `APP_SRV_BPM.dbo.表名` 和 `APP_SRV_COMMON.dbo.表名` 存取不同資料庫
- 簡化 datasource 管理

**關鍵設定**：
- 必須加上 `driverClassName: com.microsoft.sqlserver.jdbc.SQLServerDriver`
- 使用 JDBC Driver 7.4.1.jre8（較新版本 12.x 連線失敗）
- 使用 IP `10.136.158.140` 而非 hostname（container 內 DNS 解析問題）

**放棄選項**：
- 分開建立 `mssql_bpm` 和 `mssql_common`（不需要）
- 使用 JDBC Driver 12.x（連線失敗）
- 使用 hostname `twtpesqldv2.delta.corp`（DNS 解析不穩定）

---

### 2024-12-17: 新增 PostgreSQL 連線

**決策**：新增 `postgres_cleaned_data` datasource

**連線資訊**：
- Host: `10.136.218.208:5505`
- Database: `cleaned_data_db`

**用途**：未來可能需要從 PostgreSQL 同步資料
