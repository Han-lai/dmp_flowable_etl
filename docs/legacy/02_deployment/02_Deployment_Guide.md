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

#### 第三步：啟動 監控 (選配)
```bash
docker-compose -f infra/monitoring/docker-compose.yml up -d
```

#### 第四步：初始化資料管線 (首次部署必執行)
> **注意**: 第四步僅在「全新部署」或「需要完整重建整條管線」時執行。日常運維請參考 [第 3 節](#3-數據同步與流程維護-data-operations)。

```bash
# 步驟 4-1: 建立 Bronze/Silver/Gold 層所有空表與 Materialized View
python scripts/etl/execute_etl.py

# 步驟 4-2: 初次抽取 MSSQL 資料進入 ClickHouse Bronze 層
# (須確保 execute_etl.py 已完成，Bronze 表存在後方可執行)
python scripts/etl/sync_unified.py --table all
```

---

## 3. 數據同步與流程維護 (Data Operations)

### 3.1 核心數據同步 (Python ETL)
主力同步腳本為 `sync_unified.py`，負責透過 JDBC Bridge 將 MSSQL 資料抽取至 ClickHouse Bronze 層。

| 策略 | 適用表 | 說明 |
| :--- | :--- | :--- |
| **Batch (增量)** | `taskinst`, `varinst`, `procinst`, `identitylink` | 依浮水印 (Watermark) 追蹤上次同步時間，僅抽取新資料 |
| **Full (全量)** | `procdef`, MDM, HR 維度表 | 每次 Truncate 後重新全量載入 |

**手動執行範例**:
```bash
# 同步所有表 (自動判斷策略)
python scripts/etl/sync_unified.py --table all

# 同步單一大表 (指定起始日)
python scripts/etl/sync_unified.py --table taskinst --start 2025-01-01

# 只更新 Silver / Gold 轉換層 (Bronze 資料不動)
python scripts/etl/execute_etl.py --skip-existing
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
| **JDBC Bridge 連線失敗 (NamedDataSource does not exist)** | 1. JSON Key 命名不符<br>2. JAR 版本不相容<br>3. 服務未重啟 | 1. 檢查 `mssql_master.json` 第一層 Key 必須為 `"mssql_master"`<br>2. **強烈建議使用 mssql-jdbc v8.x** (v11 可能導致 Code 86 錯誤)<br>3. 執行 `docker-compose restart jdbc-bridge` |

### 4.2 內網離線環境部署 (Offline JDBC Configuration)
若部署環境**無法連線外部網際網路**(例如無法從 Maven Repo 下載 JDBC Driver)，請按以下步驟改用「本地 JAR 檔」：

1. **放置 JAR 檔**: 將下載好的 `.jar` 檔 (強烈建議使用 **mssql-jdbc-8.2.2.jre8.jar**) 放入實體機目錄 `infra/clickhouse/jdbc-bridge/drivers/` 內。
2. **修改設定檔**: 打開 `infra/clickhouse/jdbc-bridge/config/datasources/mssql_master.json`。
3. **更改路徑**: 將 `driverUrls` 裡面的 `http://...` 網址，改為 Docker 內部掛載的絕對路徑：
   ```json
   "driverUrls": [
     "/app/drivers/mssql-jdbc-xx.jar"
   ]
   ```
4. **重啟服務**: 執行 `docker-compose -f infra/clickhouse/docker-compose.yml restart jdbc-bridge` 使設定生效。

### 4.3 API 代碼更新流程
1.  透過 FileBrowser/SSH 修改 `api/main.py`。
2.  執行容器重啟：`docker restart flowable_pipeline_api`。
3.  驗證日誌：`docker logs -f flowable_pipeline_api`。

---

## 5. 變更紀錄 (Change Log)

*   **2026-03-10 (v4.0)**: 重整為 `infra/` 中心化架構，移除所有 `v2` 標籤，落實 Split-Stack 部署指南。
*   **2026-02-09 (v2.1)**: 確立 Refreshable MView 機制，最佳化每小時刷新邏輯。
*   **2026-02-03 (v1.1)**: 完成 L5 指標對齊，建立初代 E2E 技術文件。
