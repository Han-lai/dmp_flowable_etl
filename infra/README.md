# 基礎設施中心 (Infrastructure Center - Split-Stack)

本目錄為系統所有基礎設施的集中管理中心，採用服務拆分 (Split-Stack) 架構，確保各模組獨立部署與維護。

---

## 1. 目錄結構 (Directory Structure)

```text
infra/
├── clickhouse/             # 數據倉儲堆疊 (ClickHouse + Native ODBC)
│   ├── odbc/               # 客製 image、docker-compose-odbc.yml、odbc.ini
│   ├── config.d/           # Server 層級設定檔
│   └── users.d/            # User 層級設定檔
├── api/                    # 應用服務堆疊 (FastAPI L5 API)
├── cube/                   # 語義層堆疊 (Cube.js)
└── monitoring/             # 監控預警堆疊 (Prometheus + Grafana)
```

詳細的容器架構、ODBC 連線設定、config.d/users.d 設定檔說明與完整部署步驟，請見 [`docs/ClickHouse 基礎設施建置文件.md`](<../docs/ClickHouse 基礎設施建置文件.md>)。

---

## 2. 四大堆疊啟動流程 (Service Setup)

### A. 數據倉儲 (ClickHouse Stack)
負責核心資料存儲與 MSSQL ODBC 橋接。
1. 建立 `infra/.env`（連線資訊，不進版控）
2. 啟動服務: `docker-compose -f infra/clickhouse/odbc/docker-compose-odbc.yml up -d`

*完整建置步驟、設定檔說明見 [`docs/ClickHouse 基礎設施建置文件.md`](<../docs/ClickHouse 基礎設施建置文件.md>)。*

### B. 應用服務 (API Stack)
負責提供 L5 Insight 數據接口。
1. 進入目錄: `cd infra/api`
2. 啟動服務: `docker-compose up -d`
3. 預設存取: `http://localhost:7088/docs` (Swagger UI)

### C. 語義層服務 (Cube Stack)
負責提供 Headless BI 語義建模與 API。
1. 進入目錄: `cd infra/cube`
2. 啟動服務: `docker-compose up -d`
3. 預設存取: `http://localhost:4002` (API), `http://localhost:4003` (Playground)

### D. 監控系統 (Monitoring Stack)
負責效能觀測與自動化預警。
1. 進入目錄: `cd infra/monitoring`
2. 啟動服務: `docker-compose up -d`
3. 預設存取:
    - Grafana: `http://localhost:9003`
    - Prometheus: `http://localhost:9011`

---

## 3. 關鍵維運指令 (Quick Ops)

- **檢查所有容器**: `docker ps --filter "name=flowable"`
- **重啟 ClickHouse**: `docker-compose -f infra/clickhouse/odbc/docker-compose-odbc.yml restart`
- **查看 API 日誌**: `docker-compose -f infra/api/docker-compose.yml logs -f`
