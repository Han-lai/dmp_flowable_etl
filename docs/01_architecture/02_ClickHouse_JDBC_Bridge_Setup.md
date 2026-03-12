# ClickHouse 與 JDBC Bridge 架設配置手冊

本手冊專注於 ClickHouse 資料倉儲的基礎架設、JDBC Bridge 跨庫連線的建立流程，以及相關的驅動相容性配置。

---

## 1. ClickHouse 與 JDBC Bridge 部署 (Docker)
系統採用 Docker Compose 進行多容器管理。核心包含 ClickHouse Server 與 JDBC Bridge，此架構確保了資料存儲與跨庫抓取引擎的解耦。

### **1.1 Docker Compose 核心配置 (`docker-compose.yml`)**
```yaml
services:
  # ClickHouse Server: 數據存儲與運算核心
  clickhouse:
    image: clickhouse/clickhouse-server:24.3
    ports:
      - "8121:8123"   # HTTP 介面 (API & CubeJS 使用)
      - "9001:9000"   # 原生 TCP 介面 (ETL 腳本使用)
    volumes:
      - clickhouse-data:/var/lib/house
      - ${VOLUMES_ROOT}/clickhouse/config:/var/lib/clickhouse/server/config.d
    ulimits:
      nofile: { soft: 262144, hard: 262144 }

  # JDBC Bridge: 跨庫數據抓取引擎
  jdbc-bridge:
    image: clickhouse/jdbc-bridge:2.1.0
    ports:
      - "9019:9019"
    volumes:
      - ${VOLUMES_ROOT}/clickhouse/jdbc-bridge/config/datasources:/etc/clickhouse-jdbc-bridge/config/datasources
      - ${VOLUMES_ROOT}/clickhouse/jdbc-bridge/drivers:/app/drivers
    depends_on:
      - clickhouse
```

---

## 2. JDBC Bridge 跨庫連線建立 (Establishment)
此組件負責讓 ClickHouse 能夠直接查詢遠端 MSSQL。

### **2.1 資料源定義 (`mssql_master.json`)**
在此檔案中定義連線字串與憑證，驅動路徑必須指向容器內的掛載位置。
```json
{
  "mssql_master": {
    "driverUrls": [
      "file:///etc/clickhouse-jdbc-bridge/drivers/mssql-jdbc-11.2.3.jre8.jar"
    ],
    "driverClassName": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
    "jdbcUrl": "jdbc:sqlserver://10.136.x.x:65000;database=APP_SRV_BPM;encrypt=true;trustServerCertificate=true",
    "username": "APP_SRV_BPM",
    "password": "YOUR_PASSWORD"
  }
}
```

### **2.2 重要：JRE 版本與驅動手動配置**
由於 ClickHouse JDBC Bridge 容器內部的 Java 運行環境 (JRE8) 與最新版 JDBC 驅動可能存在相容性問題，必須遵循以下安裝規範：

1.  **驅動版本選擇**：必須使用 **JRE8** 版本（例如 `mssql-jdbc-11.2.3.jre8.jar`）。使用更高版本的 JRE 驅動（如 jre11/jre17）可能會導致 Bridge 無法正確載入類別。
2.  **手動存放路徑**：
    *   外部路徑：`${VOLUMES_ROOT}/clickhouse/jdbc-bridge/drivers/`
    *   操作方式：需手動將下載的 `.jar` 檔放入上述目錄，該目錄會在啟動時掛載。
3.  **連線參數安全性**：`trustServerCertificate=true` 必須開啟，以跳過內部伺服器 SSL 憑證驗證，確保連線不被阻斷。

---

## 3. 基礎設施環境變數 (`.env`)
所有目錄掛載均透過 `${VOLUMES_ROOT}` 動態控制，確保環境遷移的一致性。

```bash
# 宿主機路徑根目錄 (掛載點)
VOLUMES_ROOT=/home/docker-data/flowable_pipeline_api
```

---
**文件維護資訊**
*   **版本號**：v1.0.0
*   **更新日期**：2026-03-12
*   **維護人員**：albee
