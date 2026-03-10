# ClickHouse + JDBC Bridge 部署指南

## 目錄結構

```
docker/
├── docker-compose.yml              # Docker Compose 部署設定
├── clickhouse/
│   ├── config/
│   │   ├── jdbc_bridge.xml         # JDBC Bridge 連線設定
│   │   └── merge_settings.xml      # MergeTree 效能調校
│   └── users/                      # 使用者設定（可選）
└── jdbc-bridge/
    ├── config/
    │   └── datasources/
    │       ├── mssql_bpm.json      # APP_SRV_BPM 連線設定
    │       └── mssql_common.json   # APP_SRV_COMMON 連線設定
    └── drivers/
        └── mssql-jdbc-12.4.2.jre11.jar
```

## 服務元件

| 服務 | Image | Port | 用途 |
|------|-------|------|------|
| ClickHouse | `clickhouse/clickhouse-server:24.3` | `8121` (HTTP), `9001` (TCP) | 資料倉儲 |
| JDBC Bridge | `clickhouse/jdbc-bridge:2.1.0` | `9019` | MSSQL 連線橋接 |

## 前置準備

### 下載 MSSQL JDBC Driver

```powershell
# 從 Maven 下載 JDBC Driver
curl -L -o docker/jdbc-bridge/drivers/mssql-jdbc-12.4.2.jre11.jar ^
  "https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/12.4.2.jre11/mssql-jdbc-12.4.2.jre11.jar"
```

## 啟動服務

```powershell
cd docker

# 啟動所有服務
docker compose up -d

# 查看服務狀態
docker compose ps

# 查看 logs
docker compose logs -f
```

## 驗證連線

### 1. 測試 ClickHouse

```powershell
curl "http://localhost:8121/?query=SELECT%201"
```

### 2. 測試 JDBC Bridge → MSSQL

```sql
-- 在 ClickHouse 中執行
SELECT * FROM jdbc('mssql_bpm', 'SELECT 1 as test');

-- 查詢 MSSQL 資料表
SELECT * FROM jdbc('mssql_bpm', 'SELECT TOP 5 * FROM ACT_HI_PROCINST');
```

## 停止服務

```powershell
docker compose down        # 停止服務
docker compose down -v     # 停止並刪除資料
```

## 常見問題

### JDBC Bridge 無法連線到 MSSQL
1. 確認 MSSQL Server 允許遠端連線
2. 確認防火牆開放對應 port
3. 檢查 `jdbc-bridge/config/datasources/*.json` 連線資訊

### ClickHouse 無法連線到 JDBC Bridge
1. 確認 `jdbc-bridge` container 正常運行
2. 確認兩個 container 在同一個 `clickhouse-net` network

### 找不到 JDBC Driver
確認 `mssql-jdbc-12.4.2.jre11.jar` 已放置在 `jdbc-bridge/drivers/`
