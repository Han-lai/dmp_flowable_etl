# Project Context

## 用途
記錄專案的「現狀」，讓 AI Agent 快速理解背景。

## 何時更新
- 專案目標改變時
- 資料來源改變時
- 技術棧改變時

## ❌ 不該寫的內容
- 未來計畫
- 可能的需求
- 優化方向

---

## 專案名稱
DMP Flowable 資料同步

## 當前階段
Exploration / MVP

## 專案目標
1. 探索真實 MSSQL 資料表結構
2. 建立本機 MSSQL Docker Sandbox 測試環境
3. 將 MSSQL 資料同步到 ClickHouse Bronze 層

## 資料來源

| Database | 用途 | 表數量 |
|----------|------|--------|
| APP_SRV_BPM | Flowable 流程資料 | 5 |
| APP_SRV_COMMON | DMP 人員/組織資料 | 11 |

## 技術棧
- 來源：MSSQL Server（真實 + Mock Docker）
- 目標：ClickHouse
- 同步方式：JDBC Bridge
- 部署：Docker Compose / Portainer

## Docker 服務

| 服務 | 位置 | 用途 |
|------|------|------|
| ClickHouse + JDBC Bridge | `docker/docker-compose.yml` | 資料倉儲 |
| MSSQL Mock | `docker/mssql-mock/docker-compose.yml` | 本機測試 |

## 連線資訊

### ClickHouse（VM）
- Host: REDACTED_IP
- Port: 8123
- User: default
- Password: clickhouse123

### MSSQL Mock（本機）
- Host: localhost
- Port: 1433
- User: sa
- Password: YourStrong@Passw0rd

## 目前狀態
- [x] MSSQL 連線測試完成
- [x] 資料表結構探索完成（16 張表，完整 schema）
- [x] Bronze 層 DDL 建立完成
- [x] 同步 SQL 腳本建立完成
- [x] ClickHouse Docker 部署完成（VM）
- [x] MSSQL Mock Docker 設定完成（完整 schema）
- [ ] MSSQL Mock 實際部署
- [ ] JDBC Bridge datasource 設定
- [ ] 首次全量同步執行
