# MSSQL → ClickHouse 同步操作手冊

## 1. 執行同步

```powershell
python sync/sync_to_clickhouse.py
```

結果會輸出到 `logs/sync_result_YYYYMMDD_HHMMSS.txt`

## 2. 執行驗證

```powershell
python validation/validate_sync.py
```

結果會輸出到 `logs/validation_report_YYYYMMDD_HHMMSS.txt`

## 3. 連線資訊

### ClickHouse
- Host: 10.136.218.207
- Port: 8121
- User: default
- Password: default

### MSSQL（透過 JDBC Bridge）
- Datasource: mssql_master
- 可查詢: APP_SRV_BPM.dbo.*, APP_SRV_COMMON.dbo.*

## 4. 常用查詢

```sql
-- 查看 bronze 表
SHOW TABLES FROM bronze;

-- 查看資料量
SELECT database, table, sum(rows) as rows
FROM system.parts
WHERE database = 'bronze' AND active
GROUP BY database, table
ORDER BY rows DESC;

-- 測試 JDBC 連線
SELECT * FROM jdbc('mssql_master', 'SELECT 1 as test');
```

## 5. 常見問題

### Q1: Nullable 欄位當 ORDER BY
使用 `tuple()` 避免。

### Q2: JDBC Bridge 連線失敗
確認 `driverClassName` 有設定。

### Q3: 資料筆數有差異
正常現象，MSSQL 是生產資料庫，資料持續變動。
