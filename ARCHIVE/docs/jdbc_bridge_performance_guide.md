# JDBC Bridge 同步效能量測指南

> 建立日期: 2026-01-12
> 適用架構: MSSQL → JDBC Bridge → ClickHouse Bronze

---

## A. 效能量測指標設計

### 1. Query Latency（同步耗時）

| 指標 | 定義 | 計算方式 |
|------|------|----------|
| **單次同步耗時** | 單張表從開始到完成的時間 | `query_duration_ms` from system.query_log |
| **總同步耗時** | 所有表同步完成的總時間 | Python 腳本已記錄 (`total_duration`) |
| **吞吐量 (rows/sec)** | 每秒同步筆數 | `written_rows / (query_duration_ms / 1000)` |
| **吞吐量 (MB/sec)** | 每秒同步資料量 | `written_bytes / (query_duration_ms / 1000) / 1024 / 1024` |

### 2. Data Freshness（資料新鮮度）

| 指標 | 定義 | 計算方式 |
|------|------|----------|
| **MSSQL 最新時間** | 來源表最新資料的時間戳 | `MAX(tracking_col)` via JDBC |
| **ClickHouse 最新時間** | Bronze 表最新資料的時間戳 | `MAX(_sync_time)` |
| **資料延遲 (lag_seconds)** | 兩者的時間差 | `now() - MAX(tracking_col)` |
| **同步延遲** | 上次同步到現在的時間 | `now() - last_sync_time` from watermark |

---

## B. ClickHouse 端量測 SQL

### B.1 查詢最近 24 小時的 JDBC Bridge 同步紀錄

```sql
-- 找出所有 JDBC Bridge 相關的查詢（近 24 小時）
SELECT
    event_time,
    query_duration_ms,
    read_rows,
    read_bytes,
    written_rows,
    written_bytes,
    memory_usage,
    query_kind,
    tables,
    substring(query, 1, 200) AS query_preview
FROM system.query_log
WHERE event_time > now() - INTERVAL 24 HOUR
  AND type = 'QueryFinish'
  AND query LIKE '%jdbc(%'
ORDER BY event_time DESC
LIMIT 100;
```

### B.2 計算 p50 / p95 同步效能

```sql
-- 計算 JDBC Bridge 查詢的效能統計
SELECT
    count() AS query_count,
    
    -- 耗時統計 (ms)
    round(avg(query_duration_ms), 2) AS avg_duration_ms,
    round(quantile(0.5)(query_duration_ms), 2) AS p50_duration_ms,
    round(quantile(0.95)(query_duration_ms), 2) AS p95_duration_ms,
    round(max(query_duration_ms), 2) AS max_duration_ms,
    
    -- 資料量統計
    sum(written_rows) AS total_written_rows,
    round(sum(written_bytes) / 1024 / 1024, 2) AS total_written_mb,
    
    -- 吞吐量統計
    round(sum(written_rows) / (sum(query_duration_ms) / 1000), 2) AS avg_rows_per_sec,
    round(sum(written_bytes) / (sum(query_duration_ms) / 1000) / 1024 / 1024, 2) AS avg_mb_per_sec,
    
    -- 記憶體統計
    round(avg(memory_usage) / 1024 / 1024, 2) AS avg_memory_mb,
    round(max(memory_usage) / 1024 / 1024, 2) AS max_memory_mb

FROM system.query_log
WHERE event_time > now() - INTERVAL 24 HOUR
  AND type = 'QueryFinish'
  AND query LIKE '%jdbc(%'
  AND query_kind = 'Insert';
```

### B.3 按表分組的同步效能

```sql
-- 按目標表分組的同步效能
SELECT
    -- 從 query 中提取目標表名
    extract(query, 'INTO ([a-z_\.]+)') AS target_table,
    count() AS sync_count,
    round(avg(query_duration_ms), 2) AS avg_duration_ms,
    round(quantile(0.95)(query_duration_ms), 2) AS p95_duration_ms,
    sum(written_rows) AS total_rows,
    round(sum(written_bytes) / 1024 / 1024, 2) AS total_mb,
    round(sum(written_rows) / (sum(query_duration_ms) / 1000), 2) AS rows_per_sec
FROM system.query_log
WHERE event_time > now() - INTERVAL 7 DAY
  AND type = 'QueryFinish'
  AND query LIKE '%jdbc(%'
  AND query_kind = 'Insert'
GROUP BY target_table
ORDER BY total_rows DESC;
```

### B.4 Top 20 最慢同步任務

```sql
-- Top 20 最慢的 JDBC Bridge 同步
SELECT
    event_time,
    query_duration_ms,
    written_rows,
    round(written_bytes / 1024 / 1024, 2) AS written_mb,
    round(written_rows / (query_duration_ms / 1000), 2) AS rows_per_sec,
    round(memory_usage / 1024 / 1024, 2) AS memory_mb,
    substring(query, 1, 300) AS query_preview
FROM system.query_log
WHERE event_time > now() - INTERVAL 7 DAY
  AND type = 'QueryFinish'
  AND query LIKE '%jdbc(%'
  AND query_kind = 'Insert'
ORDER BY query_duration_ms DESC
LIMIT 20;
```

### B.5 資料新鮮度檢查

```sql
-- 檢查各 Bronze 表的資料新鮮度
SELECT
    'bronze.bpm_act_hi_taskinst' AS table_name,
    max(LAST_UPDATED_TIME_) AS max_source_time,
    max(_sync_time) AS max_sync_time,
    dateDiff('second', max(LAST_UPDATED_TIME_), now()) AS lag_seconds,
    dateDiff('minute', max(LAST_UPDATED_TIME_), now()) AS lag_minutes
FROM bronze.bpm_act_hi_taskinst

UNION ALL

SELECT
    'bronze.bpm_act_hi_procinst',
    max(START_TIME_),
    max(_sync_time),
    dateDiff('second', max(START_TIME_), now()),
    dateDiff('minute', max(START_TIME_), now())
FROM bronze.bpm_act_hi_procinst

UNION ALL

SELECT
    'bronze.bpm_act_hi_varinst',
    max(LAST_UPDATED_TIME_),
    max(_sync_time),
    dateDiff('second', max(LAST_UPDATED_TIME_), now()),
    dateDiff('minute', max(LAST_UPDATED_TIME_), now())
FROM bronze.bpm_act_hi_varinst;
```

### B.6 Watermark 狀態檢查

```sql
-- 檢查 Watermark 表的同步狀態
SELECT
    table_name,
    last_sync_time,
    sync_time,
    row_count,
    dateDiff('minute', sync_time, now()) AS minutes_since_sync
FROM bronze._sync_watermark FINAL
ORDER BY sync_time DESC;
```

---

## C. Incremental vs Full Refresh 效能特徵

### C.1 效能比較

| 特徵 | Incremental | Full Refresh |
|------|-------------|--------------|
| **資料量** | 只同步增量 (通常 < 1%) | 全表資料 |
| **耗時** | 快 (秒級) | 慢 (分鐘級) |
| **MSSQL 負載** | 低 (WHERE 條件過濾) | 高 (全表掃描) |
| **ClickHouse 負載** | 低 (INSERT) | 高 (DROP + CREATE) |
| **適用場景** | 日常同步 | 首次同步、資料修復 |

### C.2 你的環境實測數據

根據 `CLAUDE.md` 記錄：

| 方式 | 耗時 | 資料量 |
|------|------|--------|
| 全量同步 | ~68 秒 | 2,134,433 筆 |
| 增量同步 | ~10 秒 | 增量資料 |

**吞吐量估算**：
- 全量: 2,134,433 / 68 ≈ **31,389 rows/sec**
- 這是相當不錯的效能

### C.3 何時用 Incremental？

✅ 適合 Incremental：
- 表有可靠的追蹤欄位 (LAST_UPDATED_TIME_, CREATE_TIME_)
- 資料量大 (> 10K rows)
- 需要頻繁同步 (每小時/每天)

❌ 不適合 Incremental：
- 無追蹤欄位
- 資料會被 UPDATE/DELETE（追蹤欄位無法捕捉）
- 資料量小 (< 1K rows)

### C.4 Full Refresh 瓶頸

Full Refresh 可能成為瓶頸的情況：
1. **MSSQL 端**：全表掃描造成 IO 壓力
2. **網路**：大量資料傳輸
3. **ClickHouse 端**：DROP + CREATE 造成短暫不可用

---

## D. 瓶頸判讀指南

### D.1 判讀表

| 現象 | 可能原因 | 判讀方式 |
|------|----------|----------|
| `query_duration_ms` 高，`written_rows` 低 | MSSQL 查詢慢或網路延遲 | 檢查 MSSQL 執行計畫 |
| `rows_per_sec` < 10,000 | JDBC Bridge 瓶頸或網路慢 | 比較直連 MSSQL 的速度 |
| `rows_per_sec` > 30,000 | 正常，效能良好 | - |
| `memory_usage` 很高 | 大量資料一次載入 | 考慮分批同步 |
| `lag_seconds` > 86400 (1天) | 同步未執行或失敗 | 檢查 watermark 和 log |
| `lag_seconds` < 3600 (1小時) | 正常，資料新鮮 | - |

### D.2 效能基準線（你的環境）

根據現有數據，建議的基準線：

| 指標 | 正常範圍 | 警告閾值 | 嚴重閾值 |
|------|----------|----------|----------|
| 增量同步耗時 | < 30 秒 | > 60 秒 | > 300 秒 |
| 全量同步耗時 | < 120 秒 | > 300 秒 | > 600 秒 |
| rows/sec | > 20,000 | < 10,000 | < 5,000 |
| 資料延遲 (lag) | < 1 小時 | > 4 小時 | > 24 小時 |

---

## E. 最小改善建議

### E.1 不改架構的優化方向

1. **JDBC Fetch Size 調整**
   - 預設 fetch size 可能太小
   - 在 JDBC Bridge 設定中增加 `fetchSize=10000`
   - 位置: `docker/jdbc-bridge/config/datasources/mssql_master.json`

2. **WHERE 條件優化**
   - 確保 MSSQL 端的追蹤欄位有索引
   - 避免在 WHERE 中使用函數轉換

3. **批次策略**
   - 大表考慮分批同步（按日期範圍）
   - 避免單次同步超過 100 萬筆

### E.2 何時考慮改用其他方式？

| 情況 | 建議 |
|------|------|
| 需要即時同步 (< 1 分鐘延遲) | 考慮 CDC (Debezium + Kafka) |
| 資料量 > 1000 萬筆 | 考慮 Airbyte 或 Spark |
| MSSQL 負載過高 | 考慮讀取副本 |
| 需要 DELETE 同步 | 考慮 CDC 或定期全量 |

**目前狀態評估**：
- 增量同步 ~10 秒，全量 ~68 秒
- 吞吐量 ~31K rows/sec
- **結論：目前 JDBC Bridge 效能合理，不需要改架構**

---

## F. 最小執行流程

### Step 1: 執行同步並記錄時間

```bash
# 執行增量同步
python sync/sync_incremental.py all
```

### Step 2: 查詢 ClickHouse query_log

```sql
-- 執行 B.2 的 SQL 取得效能統計
```

### Step 3: 檢查資料新鮮度

```sql
-- 執行 B.5 的 SQL 檢查 lag
```

### Step 4: 產出結論

比較以下數據：
- Python 腳本記錄的耗時 vs query_log 的 query_duration_ms
- 如果差異 < 10%：瓶頸在 ClickHouse/JDBC Bridge
- 如果差異 > 30%：瓶頸在 Python 腳本或網路

---

## G. 已知效能數據（你的環境）

| 指標 | 數值 | 來源 |
|------|------|------|
| 全量同步耗時 | 68 秒 | CLAUDE.md |
| 增量同步耗時 | 10 秒 | CLAUDE.md |
| 總資料量 | 2,134,433 筆 | CLAUDE.md |
| 吞吐量 | ~31,389 rows/sec | 計算值 |
| Bronze 表數 | 16 張 | CLAUDE.md |
| 增量表數 | 5 張 | sync_incremental.py |
| 全量表數 | 11 張 | sync_incremental.py |

---

## H. 結論

**目前 JDBC Bridge 從 MSSQL 同步 Bronze 的效能評估：**

1. **效能合理**：~31K rows/sec 是不錯的吞吐量
2. **延遲可控**：增量同步 ~10 秒，不會成為瓶頸
3. **對下游影響**：
   - Silver RMV 每日刷新，不受 Bronze 同步影響
   - Cube.js 讀取 RMV，與 Bronze 同步解耦
   - Gold 快照手動執行，可在 Bronze 同步後執行

**建議**：維持現有架構，定期監控 query_log 確保效能穩定。
