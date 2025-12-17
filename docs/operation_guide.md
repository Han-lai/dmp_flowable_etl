# MSSQL → ClickHouse 同步操作手冊

## 0. JDBC Bridge Datasource 設定

### 目錄結構

```
jdbc-bridge/
├── config/
│   └── datasources/
│       ├── mssql_master.json
│       └── postgres_cleaned_data.json
└── drivers/
    └── (保持空白，使用網路下載)
```

### MSSQL Datasource 設定（mssql_master.json）

```json
{
  "mssql_master": {
    "driverUrls": ["https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/7.4.1.jre8/mssql-jdbc-7.4.1.jre8.jar"],
    "driverClassName": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
    "jdbcUrl": "jdbc:sqlserver://10.136.158.140:1433;databaseName=master;encrypt=false;trustServerCertificate=true",
    "username": "DMP_APP_SRV",
    "password": "APP@DB#01"
  }
}
```

**重要**：
- `driverClassName` 是必要的，否則連線會失敗
- 使用 7.4.1.jre8 版本（較新版本可能失敗）
- 使用 IP 而非 hostname

### PostgreSQL Datasource 設定（postgres_cleaned_data.json）

```json
{
  "postgres_cleaned_data": {
    "driverUrls": ["https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.1/postgresql-42.7.1.jar"],
    "jdbcUrl": "jdbc:postgresql://10.136.218.208:5505/cleaned_data_db",
    "username": "dbtuser",
    "password": "pssd"
  }
}
```

### 測試連線

在 ClickHouse 執行：

```sql
-- 測試 MSSQL
SELECT * FROM jdbc('mssql_master', 'SELECT 1 as test')

-- 測試 PostgreSQL
SELECT * FROM jdbc('postgres_cleaned_data', 'SELECT 1 as test')

-- 查詢 MSSQL 資料庫
SELECT * FROM jdbc('mssql_master', 'SELECT TOP 10 * FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST')
```

---

## 1. 環境啟動

### 啟動 Docker 服務

```powershell
cd docker
docker-compose up -d
```

### 確認服務狀態

```powershell
docker-compose ps
# 應該看到 clickhouse-server 和 clickhouse-jdbc-bridge 都是 Up 狀態
```

### 停止服務

```powershell
docker-compose down
```

---

## 2. 初始化 ClickHouse

### 建立 Database 與表

```powershell
# 進入 ClickHouse client
docker exec -it clickhouse-server clickhouse-client

# 執行初始化腳本
cat sql/01_create_database.sql | docker exec -i clickhouse-server clickhouse-client
cat sql/02_create_bpm_tables.sql | docker exec -i clickhouse-server clickhouse-client
cat sql/03_create_common_tables.sql | docker exec -i clickhouse-server clickhouse-client
```

---

## 3. 執行同步

### Full Load（全量同步）

```powershell
# 同步 Flowable 表
cat sync/full_load_bpm.sql | docker exec -i clickhouse-server clickhouse-client

# 同步 DMP 表
cat sync/full_load_common.sql | docker exec -i clickhouse-server clickhouse-client
```

### Incremental Load（增量同步）

```powershell
cat sync/incremental_load.sql | docker exec -i clickhouse-server clickhouse-client
```

---

## 4. 資料驗證

### Row Count 比對

```powershell
cat validation/row_count_check.sql | docker exec -i clickhouse-server clickhouse-client
```

### 資料品質檢查

```powershell
cat validation/data_quality_check.sql | docker exec -i clickhouse-server clickhouse-client
```

---

## 5. 常見問題排除

### Q1: JDBC Bridge 無法連線到 MSSQL

**症狀：** `jdbc()` 函數執行時報錯，或 log 顯示 `Failed to add NamedDataSource`

**解決方案：**
1. 確認 datasource JSON 格式正確（無特殊字元）
2. **必須加上 `driverClassName`**：
   ```json
   "driverClassName": "com.microsoft.sqlserver.jdbc.SQLServerDriver"
   ```
3. 使用 JDBC Driver **7.4.1.jre8**（較新版本可能失敗）
4. 使用 IP 而非 hostname（container 內 DNS 可能無法解析）
5. 確認防火牆開放 1433 port

### Q2: ClickHouse 無法連線到 JDBC Bridge

**症狀：** `Code: 279. DB::Exception: jdbc-bridge is not running`

**解決方案：**
1. 確認 jdbc-bridge container 正常運行
2. 檢查 `docker/clickhouse/config/jdbc_bridge.xml`
3. 重啟服務：`docker-compose restart`

### Q3: 同步資料筆數不一致

**可能原因：**
1. 同步期間 MSSQL 有新資料寫入
2. 增量同步時間範圍設定問題

**解決方案：**
1. 執行 Full Load 重新同步
2. 檢查 `bronze._sync_log` 確認同步狀態

### Q4: 所有 Datasource 都載入失敗

**症狀：** Log 顯示所有 datasource 都 `Failed to add`

**可能原因：**
1. `drivers/` 目錄有損壞的 jar 檔
2. JSON 檔案有不可見的特殊字元（如 non-breaking space）

**解決方案：**
1. 清空 `drivers/` 目錄
2. 重新建立 JSON 檔案（用 `cat << 'EOF'` 避免特殊字元）
3. 重啟 jdbc-bridge container

### Q5: 密碼含特殊字元導致 JSON 解析錯誤

**症狀：** 密碼含 `@` 或 `#` 時，shell echo 指令會解析錯誤

**解決方案：**
使用 heredoc 避免特殊字元被解析：
```bash
cat > datasources/mssql_master.json << 'EOF'
{
  "mssql_master": {
    "password": "APP@DB#01"
  }
}
EOF
```

---

## 6. 監控指令

### 查看同步歷史

```sql
SELECT * FROM bronze._sync_log ORDER BY start_time DESC LIMIT 10;
```

### 查看各表資料量

```sql
SELECT 
    database,
    table,
    formatReadableSize(sum(bytes)) as size,
    sum(rows) as rows
FROM system.parts
WHERE database = 'bronze' AND active
GROUP BY database, table
ORDER BY rows DESC;
```
