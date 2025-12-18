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

---

### 2024-12-18: 第一階段同步完成

**成果**：
- 16 張表全量同步完成
- 總筆數：2,134,433 筆
- 同步時間：1 分 5 秒
- 平均速度：32,837 筆/秒

---

### 2024-12-18: JDBC Bridge vs Airbyte 方案比較

**決策**：建議採用「混合式方案」

**比較結果**：
| 項目 | JDBC Bridge | Airbyte |
|------|-------------|---------|
| 同步時間 | 1 分 5 秒 | 8 分 18 秒 |
| 儲存空間 | ~137 MB | ~195 MB |
| 增量同步 | 需自行開發 | 內建支援 |
| UI 管理 | 無 | 有 |

**建議**：
- 大表（歷史表、成長快速表）：Airbyte + 增量同步
- 小表或需頻繁全量刷新表：JDBC Bridge

**原因**：
- JDBC Bridge 效能優異（7.7 倍速度）
- Airbyte 提供穩定維運與增量能力
- 依表特性選擇最適方案
