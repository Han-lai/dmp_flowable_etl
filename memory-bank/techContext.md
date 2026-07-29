# 技術環境 - DMP Flowable

# 技術環境 - DMP Flowable

## ClickHouse
- **Host**: <CLICKHOUSE_HOST> (生產)
- **Port**: 8123 (生產)
- **User**: default / password: <CLICKHOUSE_PASSWORD>
- **Database**: bronze, silver, gold
- **Version**: v25.8 (生產)

## Cube.js 架構版本 (2026-05-27 更新)

| Cube | 資料來源 | 架構版本 | 查詢耗時 |
|------|---------|---------|---------|
| `L5TaskPeriodic` | `gold.rmv_l5_task_summary` | V4.3 預聚合 | 0.06~0.11s |
| `L5TaskPeriodicPivot` | `gold.rmv_l5_task_summary` | V4.3 預聚合 | 0.06~0.11s |

**重要**：兩個 Cube 的 anchor_dt（基準日計算）與資料本體均讀 `rmv_l5_task_summary FINAL`，完全不依賴 `rmv_l5_task_completion_phys`。
已知風險：ETL pipeline 中 `gold_summary` 為最後階段，ETL 執行期間 summary 可能落後 completion_phys 約數分鐘。

### Bronze 層索引優化 (2026-01-08)
**優化完成度**: 100% ✅

| 表名 | ORDER BY | Skip Index | 效能提升 | 狀態 |
|------|----------|-----------|----------|------|
| bpm_act_hi_taskinst | (PROC_INST_ID_, ID_) | START_TIME_, CLAIM_TIME_, END_TIME_ (minmax) | PROC_INST_ID_ JOIN: 68x | ✅ 已優化 |
| bpm_act_hi_varinst | (PROC_INST_ID_, NAME_, CREATE_TIME_) | TASK_ID_ (bloom_filter) | TASK_ID_ IN: 10x-50x | ✅ 已優化 |
| bpm_act_hi_procinst | PROC_INST_ID_ | - | 語義清晰度提升 | ✅ 已優化 |
| bpm_act_hi_identitylink | (TASK_ID_, USER_ID_, TYPE_) | - | 無需優化 | ✅ 已最優 |

**關鍵成就**:
- JOIN 查詢效能提升: 68x
- IN 查詢效能提升: 10x-50x
- 記憶體使用降低: 50x-200x
- 查詢併發能力提升: 10x-50x

**詳細報告**: `BRONZE_OPTIMIZATION_SUMMARY.md`

## MSSQL (Source)
- **Host**: <MSSQL_HOST>
- **Driver**: Microsoft ODBC Driver 18 for SQL Server
- **Databases**: APP_SRV_BPM, APP_SRV_COMMON
- **DSN**: `MSSQL_DSN`（設定於 `infra/clickhouse/odbc/odbc.ini`，密碼動態注入）
- **ODBC 帳號**: `APP_SRV_BPM`（`MSSQL_USER`，預設值）
- **ODBC 密碼**: 由環境變數 `MSSQL_PASSWORD` 提供，**不得以任何方式寫死**
  - 若此變數未設定（fallback 為空字串），`sync_unified_odbc.py` 仍會啟動並 TRUNCATE 目標表，但 INSERT 全部失敗，導致維度表被清空（2026-06-17/29/30 事故根因）

## S3 (MinIO)
- **Bucket**: mfg-lakehouse
- **連線資訊**: 見 `infra/.env`（不進版控）

## Python 環境
- Python 3.10+
- Virtual env: `.venv/`
- 主要套件: `clickhouse-connect`, `pyodbc`, `pymssql` (Legacy)

## 重要路徑
| 路徑 | 說明 |
|------|------|
| `scripts/etl/setup_schema.py` | 基礎架構初始化與 DDL 部署 |
| `scripts/etl/sync_unified_odbc.py` | 核心 ODBC 同步引擎 |
| `scripts/etl/execute_etl.py` | Silver/Gold 層運算引擎 (Stage 1 & 2) |
| `scripts/etl/optimize_tables.py` | 資料表優化與 FINAL 合併工具 |
| `sql/etl/` | Bronze/Silver/Gold 層 SQL 定義 |

## 同步效能追蹤

### Watermark 表 (bronze._sync_watermark)
`sync_unified_odbc.py` 會自動記錄每次同步的效能數據與真實資料跨度到 `bronze._sync_watermark` 表：

**記錄欄位**:
- `table_name`: 同步的表名
- `last_sync_time`: 最後同步的時間點（抽取端的掃描邊界，即資料的時間戳記）
- `sync_time`: 同步執行的時間（系統執行時間）
- `row_count`: **累計總筆數**（該次同步的所有批次加總）
- `duration_ms`: **累計總時間**（該次同步的所有批次時間加總，單位：毫秒）
- `min_data_time`: **資料真實最舊時間** (Nullable(DateTime64(3))) —— 2026-05-27 新增
- `max_data_time`: **資料真實最新時間** (Nullable(DateTime64(3))) —— 2026-05-27 新增

**重要說明**:
- 2026-05-27 升級：新增真實最舊與最新時間統計，在 full 或 batch 同步完成後自動統計並寫入，提供極速的水位線全域監控，並在 `execute_etl.py` 的 `--status` 監控儀表板完美呈現。
- 2026-04-02 修正：確保 `row_count` 和 `duration_ms` 都是累計值
- 修正前：`duration_ms` 只記錄最後一個批次的時間 ❌
- 修正後：`duration_ms` 累加所有批次的時間 ✅

**查詢指令**:
```bash
python scripts/etl/execute_etl.py --status
```

## 監控

### Grafana（`http://<MONITOR_HOST>:9003`，IP 見 `infra/monitoring/.env`）

| Dashboard | 用途 | Datasource |
|---|---|---|
| `Bronze Sync Monitoring` | 每日 MSSQL→Bronze 同步健康狀態，含表狀態（🔴/🟠/✅）| ClickHouse `<CLICKHOUSE_HOST>`（正式） |
| `clickhouse-l5-perf` | L5 查詢效能（CPU/記憶體/慢查詢）| ClickHouse `<MONITOR_HOST>` + Prometheus |

### Bronze 同步狀態快速診斷 SQL

```sql
-- 最後一次各表同步時間與筆數（_sync_watermark 快查）
SELECT table_name, row_count, sync_time
FROM bronze._sync_watermark
ORDER BY sync_time ASC;

-- 近期同步失敗（query_log，含完整錯誤訊息）
SELECT event_time, substring(exception,1,400) AS err
FROM system.query_log
WHERE type='ExceptionBeforeStart'
  AND query ILIKE '%bronze.%'
ORDER BY event_time DESC LIMIT 20;
```
