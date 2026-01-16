# Tech Constraints

## 用途
記錄技術限制與環境約束，避免 AI Agent 產出不可行的方案。

## 何時更新
- 發現新的技術限制時
- 環境配置改變時
- 權限改變時

## ❌ 不該寫的內容
- 希望未來解決的問題
- 理想的架構
- 效能目標

---

## 環境限制

| 項目 | 限制 |
|------|------|
| 本機 Docker | ✅ 可用（透過 Portainer） |
| MSSQL 權限 | 只有讀取權限（真實環境） |
| ClickHouse | 本機 Docker 部署 |

## 技術約束

- 同步方式：只用 Batch，不用 CDC/Kafka
- 不引入 DuckDB 或其他中介層
- 資料清洗在 ClickHouse 內完成

## 連線資訊

```
MSSQL Server: twtpesqldv2.delta.corp:1433
Database 1: APP_SRV_BPM
Database 2: APP_SRV_COMMON
```

## 已知問題

- 本機無 ODBC Driver 17，使用 SQL Server driver
- 部分表無 Primary Key（HR_Employee, FlowableTaskStats）
- Portainer 部署時相對路徑 volume 掛載可能失敗
- JDBC Bridge 需要 ClickHouse 設定 `jdbc_bridge.host` 和 `jdbc_bridge.port`

## Docker 服務狀態（2024-12-17 更新）

| 服務 | 容器名稱 | Port | 狀態 |
|------|----------|------|------|
| ClickHouse | clickhouse-server | 8123, 9001 | ✅ 運行中 |
| JDBC Bridge | clickhouse-jdbc-bridge | 9019 | ✅ 運行中，datasources 已載入 |
| MSSQL Mock | mssql-mock | 1433 | ✅ 運行中，有測試資料 |

## JDBC Bridge 連線狀態（2024-12-17）

| Datasource | 目標 | 狀態 |
|------------|------|------|
| `mssql_master` | MSSQL `10.136.158.140:1433` | ✅ 連線成功 |
| `postgres_cleaned_data` | PostgreSQL `10.136.218.208:5505` | ✅ 連線成功 |

## MSSQL JDBC Driver 限制

| Driver 版本 | 狀態 | 說明 |
|-------------|------|------|
| 12.4.2.jre11 | ❌ 失敗 | 連線失敗，原因不明 |
| 11.x | ❌ 失敗 | 連線失敗 |
| 8.4.1.jre11 | ❌ 失敗 | 連線失敗 |
| **7.4.1.jre8** | ✅ 成功 | 需加上 `driverClassName` |

**關鍵發現**：
- MSSQL datasource 必須明確指定 `driverClassName: com.microsoft.sqlserver.jdbc.SQLServerDriver`
- PostgreSQL 不需要指定 `driverClassName`（自動偵測）
- 在 `drivers/` 目錄放置本地 jar 檔會導致所有 datasource 載入失敗
