# MSSQL → ClickHouse 同步操作手冊

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

**症狀：** `jdbc()` 函數執行時報錯

**解決方案：**
1. 確認 MSSQL Server 允許遠端連線
2. 確認防火牆開放 1433 port
3. 檢查 `docker/jdbc-bridge/config/datasources/*.json` 連線資訊

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
