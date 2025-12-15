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

## Docker 服務狀態（2024-12-15）

| 服務 | 容器名稱 | Port | 狀態 |
|------|----------|------|------|
| ClickHouse | clickhouse-server | 8123, 9001 | ✅ 運行中 |
| JDBC Bridge | clickhouse-jdbc-bridge | 9019 | ⚠️ 服務啟動但 datasources 未載入 |
| MSSQL Mock | mssql-mock | 1433 | ✅ 運行中，有測試資料 |
