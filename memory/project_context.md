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
將 MSSQL 資料同步到 ClickHouse Bronze 層

## 資料來源

| Database | 用途 | 表數量 |
|----------|------|--------|
| APP_SRV_BPM | Flowable 流程資料 | 5 |
| APP_SRV_COMMON | DMP 人員/組織資料 | 11 |

## 技術棧
- 來源：MSSQL Server
- 目標：ClickHouse
- 同步方式：JDBC Bridge
- 部署：Docker Compose

## 目前狀態
- [x] MSSQL 連線測試完成
- [x] 資料表結構探索完成
- [x] Bronze 層 DDL 建立完成
- [x] 同步 SQL 腳本建立完成
- [ ] Docker 環境實際部署
- [ ] 首次全量同步執行
