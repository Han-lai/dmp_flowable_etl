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
- Host: 10.136.218.207
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
- [x] ClickHouse Docker 部署完成（本機 Portainer）
- [x] MSSQL Mock Docker 部署完成（本機）
- [x] MSSQL Mock 資料複製完成（每表 10 筆測試資料）
- [x] JDBC Bridge Docker 部署完成
- [x] JDBC Bridge datasource 設定完成（指向真實 MSSQL）
- [x] JDBC Bridge 與 ClickHouse 整合測試完成
- [x] 首次全量同步執行完成（16 張表，2,134,433 筆）
- [x] 資料驗證完成（MSSQL vs ClickHouse 比對）
- [x] JDBC Bridge vs Airbyte 方案比較完成

## 第一階段完成狀態
**完成日期**：2024-12-18

### 同步成果
| 指標 | 數值 |
|------|------|
| 同步表數 | 16 張 |
| 總筆數 | 2,134,433 筆 |
| 同步時間 | 1 分 5 秒 |
| 平均速度 | 32,837 筆/秒 |
| 儲存空間 | ~137 MB |

### 方案比較結論
- JDBC Bridge 同步速度為 Airbyte 的 **7.7 倍**
- JDBC Bridge 儲存空間節省 **30%**
- 建議採用「混合式方案」：大表用 Airbyte 增量同步，小表用 JDBC Bridge 全量同步

## 已建立的腳本

| 腳本 | 用途 |
|------|------|
| `scripts/copy_data_to_mock.py` | 從真實 MSSQL 複製資料到 Mock |
| `scripts/check_target_data.py` | 檢查 Mock MSSQL 資料 |
| `scripts/check_clickhouse.py` | 檢查 ClickHouse 狀態和表格 |
| `scripts/check_jdbc_bridge.py` | 檢查 JDBC Bridge 服務狀態 |
| `scripts/compare_databases.py` | 比較 JDBC Bridge vs Airbyte 資料 |
| `sync/sync_to_clickhouse.py` | JDBC Bridge 全量同步程式 |
| `validation/validate_sync.py` | 資料完整性驗證 |

## 下一步（第二階段）
- [ ] 實作 Incremental Load 同步
- [ ] 建立 Silver 層資料轉換
- [ ] 建立監控與告警機制
