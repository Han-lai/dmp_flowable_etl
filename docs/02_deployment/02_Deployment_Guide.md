# DMP Flowable 部署與維護手冊 (Deployment & Operations Guide)

**版本**: 4.0 (基礎設施整合與服務拆分版)  
**最後更新**: 2026-03-10  
**定位**: 本文件提供系統自環境初始化、容器部署、數據同步到故障排除的一站式指南。

---

## 1. 系統架構簡述 (Architecture Summary)

本系統採用 **Split-Stack (服務拆分)** 架構，將核心數據倉儲與 API 應用層分離，確保各組件可獨立管理：
*   **數據倉儲 (ClickHouse Stack)**: 包含 ClickHouse Server 與 JDBC Bridge。
*   **應用服務 (API Stack)**: 包含 FastAPI L5 Insight API 服務。
*   **監控層 (Monitoring Stack)**: 包含 Prometheus, Grafana 與 cAdvisor。

所有基礎設施配置均集中於 `infra/` 目錄。

---

## 2. 環境準備與部署 (Environment & Deployment)

### 2.1 目錄結構要求
在 VM 部署前，請確保以下路徑結構正確（以此範例為準）：
```text
dmp_flowable/
├── infra/                      # 基礎設施配置中心
│   ├── .env                    # 通用環境變數 (含 JDBC/DB 資訊)
│   ├── clickhouse/             # ClickHouse 堆疊 (docker-compose.yml, jdbc-bridge)
│   ├── api/                    # API 堆疊 (docker-compose.yml)
│   └── monitoring/             # 監控層 (docker-compose.yml, grafana, prometheus)
├── api/                        # API 原始碼 (掛載用)
└── sql/etl/                    # 初始化與轉換 SQL
```

### 2.2 啟動步驟 (Docker Compose)
本系統推薦使用 Docker Compose 進行部署，以確保環境一致性。

#### 第一步：啟動 ClickHouse 核心
```bash
docker-compose -f infra/clickhouse/docker-compose.yml up -d
```
*   **功能**: 啟動 ClickHouse (Port 8121/9001) 與 JDBC Bridge。

#### 第二步：啟動 API 服務 (動態掛載模式)
API 採用 Volume-mount 模式，支援代碼即修即用。
```bash
docker-compose -f infra/api/docker-compose.yml up -d
```
*   **功能**: 啟動 FastAPI (Port 7088)。容器啟動時會自動執行 `pip install -r requirements.txt`。

#### 第三步：啟動監控 (選配)
```bash
docker-compose -f infra/monitoring/docker-compose.yml up -d
```

---

## 3. 數據同步與流程維護 (Data Operations)

### 3.1 核心數據同步 (Python ETL)
數據同步腳本負責將 MSSQL 資料抽取至 ClickHouse Bronze 層。

*   **全量同步 (Master Data)**: 每日執行，清空後重載。
*   **增量同步 (BPM Table)**: 建議每小時執行一次，追蹤 `START_TIME_`。

**手動執行範例**:
```powershell
# 執行全部同步 (Bronze)
python scripts/etl/sync_batches_consolidated.py --table all

# 重建完整管線 (Silver / Gold)
python scripts/etl/execute_etl.py
```

### 3.2 ClickHouse 自動化機制
系統利用 ClickHouse **Refreshable Materialized View** 達成「免 Airflow」自動更新：
*   **更新頻率**: 每 1 小時 (由 ClickHouse 內部排程)。
*   **監控狀態**:
    ```sql
    -- 檢查黃金層刷新狀態
    SELECT name, last_refresh_time, next_refresh_time 
    FROM system.tables WHERE database = 'gold';
    ```

---

## 4. 故障排除與維運 (Troubleshooting)

### 4.1 常見問題
| 現象 | 可能原因 | 排除方法 |
| :--- | :--- | :--- |
| **API 無法連線 DB** | `.env` 配置錯誤或網路隔離 | 檢查 `infra/.env` 中的 `CLICKHOUSE_HOST` 是否為內網 IP |
| **數據量為零 (DG3/NPE)** | Vx 歸屬邏輯過時 | 確認 `sql/etl/04_silver_fact_tasks.sql` 已包含 2/26 修正 |
| **表格鎖定 (Mutation)** | 大規模刪除或修改未完成 | 使用 `KILL MUTATION WHERE mutation_id = '...'` |
| **磁碟空間不足** | 歷史日誌累積 | 檢查 `logs/` 或清理 Docker 映像 `docker system prune` |

### 4.2 API 代碼更新流程
1.  透過 FileBrowser/SSH 修改 `api/main.py`。
2.  執行容器重啟：`docker restart flowable_pipeline_api`。
3.  驗證日誌：`docker logs -f flowable_pipeline_api`。

---

## 5. 變更紀錄 (Change Log)

*   **2026-03-10 (v4.0)**: 重整為 `infra/` 中心化架構，移除所有 `v2` 標籤，落實 Split-Stack 部署指南。
*   **2026-02-09 (v2.1)**: 確立 Refreshable MView 機制，最佳化每小時刷新邏輯。
*   **2026-02-03 (v1.1)**: 完成 L5 指標對齊，建立初代 E2E 技術文件。

---

**文件負責人**: AI Antigravity  
**底層參考**: 整合原 `02_E2E_Implementation_Guide.md` 與 `DEPLOYMENT_GUIDE.md`。
