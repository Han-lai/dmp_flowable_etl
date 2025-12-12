# ClickHouse + JDBC Bridge 部署指南

## 目錄結構

```
docker/
├── docker-compose.yml          # Docker Compose 設定
├── clickhouse/
│   ├── config/
│   │   └── jdbc_bridge.xml     # JDBC Bridge 連線設定
│   └── users/                  # 使用者設定（可選）
└── jdbc-bridge/
    ├── config/
    │   └── datasources/
    │       ├── mssql_bpm.json      # APP_SRV_BPM 連線設定
    │       └── mssql_common.json   # APP_SRV_COMMON 連線設定
    └── drivers/                # JDBC Driver 放置目錄
        └── mssql-jdbc-12.4.2.jre11.jar  # 需手動下載
```

## 前置準備

### 1. 下載 MSSQL JDBC Driver

```powershell
# 下載 MSSQL JDBC Driver
# 方式 1: 從 Microsoft 官網下載
# https://learn.microsoft.com/en-us/sql/connect/jdbc/download-microsoft-jdbc-driver-for-sql-server

# 方式 2: 使用 curl 下載
curl -L -o docker/jdbc-bridge/drivers/mssql-jdbc-12.4.2.jre11.jar ^
  "https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/12.4.2.jre11/mssql-jdbc-12.4.2.jre11.jar"
```

## 啟動服務

```powershell
# 進入 docker 目錄
cd docker

# 啟動所有服務
docker-compose up -d

# 查看服務狀態
docker-compose ps

# 查看 logs
docker-compose logs -f
```

## 驗證連線

### 1. 測試 ClickHouse 連線

```powershell
# 使用 curl 測試 HTTP 介面
curl "http://localhost:8123/?query=SELECT%201"

# 或使用 clickhouse-client
docker exec -it clickhouse-server clickhouse-client
```

### 2. 測試 JDBC Bridge 連線

```sql
-- 在 ClickHouse 中執行
SELECT * FROM jdbc('mssql_bpm', 'SELECT 1 as test');

-- 測試查詢 MSSQL 資料表
SELECT * FROM jdbc('mssql_bpm', 'SELECT TOP 5 * FROM ACT_HI_PROCINST');
```

## 停止服務

```powershell
# 停止服務
docker-compose down

# 停止並刪除資料
docker-compose down -v
```

## 常見問題

### Q: JDBC Bridge 無法連線到 MSSQL

1. 確認 MSSQL Server 允許遠端連線
2. 確認防火牆開放 1433 port
3. 檢查 datasources/*.json 中的連線資訊是否正確

### Q: ClickHouse 無法連線到 JDBC Bridge

1. 確認 jdbc-bridge container 正常運行
2. 檢查 clickhouse/config/jdbc_bridge.xml 設定
3. 確認兩個 container 在同一個 network

### Q: 找不到 JDBC Driver

確認 `mssql-jdbc-12.4.2.jre11.jar` 已放置在 `jdbc-bridge/drivers/` 目錄
