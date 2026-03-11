# 基礎設施中心 (Infrastructure Center - Split-Stack)

本目錄為系統所有基礎設施的集中管理中心，採用服務拆分 (Split-Stack) 架構，確保各模組獨立部署與維護。

---

## 1. 目錄結構 (Directory Structure)

```text
infra/
├── clickhouse/             # 數據倉儲堆疊 (ClickHouse + JDBC Bridge)
│   └── README.md           # [詳細安裝手冊] 包含 JDBC 與 Driver 設定
├── api/                    # 應用服務堆疊 (FastAPI L5 API)
└── monitoring/             # 監控預警堆疊 (Prometheus + Grafana + cAdvisor)
```

---

## 2. 三大堆疊啟動流程 (Service Setup)

### A. 數據倉儲 (ClickHouse Stack)
負責核心資料存儲與 MSSQL 橋接。
1. 進入目錄: `cd infra/clickhouse`
2. 設定 `jdbc-bridge/config/datasources/mssql_master.json`
3. 啟動服務: `docker-compose up -d`
*詳細 Driver 與 Error 86 排除請見 [clickhouse/README.md](./clickhouse/README.md)。*

### B. 應用服務 (API Stack)
負責提供 L5 Insight 數據接口。
1. 進入目錄: `cd infra/api`
2. 啟動服務: `docker-compose up -d`
3. 預設存取: `http://localhost:7088/docs` (Swagger UI)

### C. 監控系統 (Monitoring Stack)
負責效能觀測與自動化預警。
1. 進入目錄: `cd infra/monitoring`
2. 啟動服務: `docker-compose up -d`
3. 預設存取: 
    - Grafana: `http://localhost:3000` (帳密預設 admin/admin)
    - Prometheus: `http://localhost:9090`

---

## 3. 關鍵維運指令 (Quick Ops)

- **檢查所有容器**: `docker ps --filter "name=flowable"`
- **重啟連線橋接**: `docker-compose -f infra/clickhouse/docker-compose.yml restart jdbc-bridge`
- **查看 API 日誌**: `docker-compose -f infra/api/docker-compose.yml logs -f`
