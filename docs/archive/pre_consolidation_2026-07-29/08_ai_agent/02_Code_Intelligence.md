# Code Intelligence（已驗證模組地圖與資料流）

**建立日期**: 2026-07-03｜**驗證方式**: 逐檔閱讀程式碼與設定檔
**標記**: ✅ 已驗證｜⚠ 推測｜❓ 尚未確認

---

## 1. 端到端資料流（✅ 全部對照程式碼驗證）

```
MSSQL APP_SRV_BPM / APP_SRV_COMMON（*_0503 後綴表，生產庫，唯讀）
  │  sync_unified_odbc.py：對每張表動態 CREATE TABLE odbc_temp_<key> ENGINE=ODBC(...)
  │  → INSERT INTO bronze.* SELECT ... FROM odbc_temp（批次表依 time_col 切 2 天窗）
  ▼
bronze（19 張表，ReplacingMergeTree(_sync_version)）
  │  execute_etl.py 依 pipeline_config.yaml 順序執行 8 個 phase，
  │  每個 phase = 一支 sql/etl/dml/*.sql 模板，以 {start_ts}/{end_ts} 分時間視窗跑
  ▼
[1] silver.mv_varinst_pivoted   ← backfill_pivot.sql   （EAV→寬表，varinst 回溯 365 天）
[2] silver.mv_fact_task_vx      ← backfill_silver.sql  （核心事實表，全部業務規則在此）
[3] silver.mv_fact_task_vx      ← backfill_exclusion.sql（補 autoComplete 排除旗標，ALTER UPDATE）
[4] gold.rmv_l5_milestone_phys  ← backfill_gold_milestone.sql（Todo/Doing/Done Bitmap 快照）
[5] gold.rmv_l5_acc_phys        ← backfill_gold_acc.sql（7 日滾動在途 Bitmap）
[6] gold.rmv_l5_task_completion_phys ← backfill_gold.sql（[4]+[5] FULL OUTER JOIN 合併）
[7] gold.rmv_l5_task_summary    ← backfill_gold_summary_historical.sql（V3 邏輯，只寫 <2026-04-01）
[8] gold.rmv_l5_task_summary    ← backfill_gold_summary.sql（V4 邏輯，只寫 ≥2026-04-01）
  ▼
Serving：
  Cube.js（4002）→ 只讀 gold.rmv_l5_task_summary FINAL（L5TaskPeriodic / L5TaskPeriodicPivot）
  FastAPI（7088）→ 讀 gold.rmv_l5_task_completion（VIEW + FINAL）
  Node BFF reports.js → 呼叫 Cube.js REST（JWT 快取簽發）
  明細鑽取 → cube_l5_task_details.js 直讀 silver.mv_fact_task_vx
```

輔助表：`bronze._sync_watermark`（同步水位線+資料時間跨度）、`ops_metrics.etl_checkpoint`（phase×window 斷點續傳）✅

---

## 2. 核心模組明細

### 2.1 `scripts/etl/sync_unified_odbc.py`（529 行）✅ 核心
- **職責**: MSSQL → Bronze 同步引擎。
- **輸入**: `config/sync_tables.yaml`（19 表）；環境變數 `CLICKHOUSE_*`、`MSSQL_USER`、`MSSQL_PASSWORD`、`ODBC_DSN`。
- **關鍵機制**:
  - 每表動態建立顯式 schema 的 `ENGINE=ODBC` 代理表（繞過 driver 對 LOB 欄位自動探測的死鎖）→ 同步完 DROP（`main()` finally）。
  - `full` 策略（15 表）：TRUNCATE → 全量 INSERT。**無回滾**（風險 R2）。
  - `batch` 策略（4 表：taskinst/varinst/procinst/identitylink）：從 watermark 續傳，依 `time_col` 切窗（`step_days: 2`）。
  - `sync_batch_adaptive()`：OOM（Code 241）/Timeout/Code 1000 → 不重試，直接把時間區間對半切遞迴，下限 30 分鐘。其他錯誤 → 重試 3 次（每次重建 client 連線）。
  - Fail-loud：任何一表 FAILED → `sys.exit(1)`（讓 `daily_etl_wrapper.sh` 的 `set -e` 生效）。
  - 每批次後更新 watermark（含 `min/max_data_time` 真實資料跨度，自動 ALTER 遷移欄位）。
- **CLI**: `--table <key|all> --start --end --step-days --step-hours --config --dry-run`。

### 2.2 `scripts/etl/execute_etl.py`（438 行）✅ 核心
- **職責**: Silver/Gold 運算引擎，讀 `pipeline_config.yaml` 依序跑 phase。
- **四種模式**: `--status`（儀表板）/ `--reset`（TRUNCATE reset_targets + checkpoint，危險）/ `--daily`（自動接龍）/ `--backfill --start --end`。
- **`--daily` 自動接龍演算法**（`main()` 3.x 段）：
  - END = taskinst watermark 的 `last_sync_time`。
  - START = `min(最後 gold_summary SUCCESS checkpoint 的 window_end, min(taskinst,varinst 的 max_data_time)) - 1 天`（取 varinst 是因 Silver JOIN 兩表，varinst 落後會產生不完整列）。無 checkpoint 時 fallback 14 天。
- **`run_safe()` 防禦**: checkpoint=SUCCESS 跳過；taskinst 該窗筆數=0 跳過**且不標 SUCCESS**（遲到資料自癒）；OOM 且窗>60 秒 → 切半遞迴（**兩半共用中點閉區間**，靠 ReplacingMergeTree 去重，避免 DateTime64 亞秒級 1 秒縫隙）；其他錯誤 → 標 FAILED 後 `sys.exit(1)`。
- **`--low-ram`**: `max_threads=1`、`max_memory_usage=10GB`、500MB 外部聚合/排序 spill、`join_algorithm='grace_hash'`。

### 2.3 `scripts/etl/setup_schema.py`（138 行）✅
- 讀 `infra_config.yaml`：建 4 個 DB（bronze/silver/gold/ops_metrics）+ 依序部署 `sql/etl/schema/` DDL。**05（dim_users）與 07（user_utilization）目前註解停用**。有 `--force` 重建。

### 2.4 `scripts/etl/daily_etl_wrapper.sh` ✅
- 每日排程入口：`set -e` → sync（--table all）→ `execute_etl.py --daily --low-ram`。**排程器與主機在 repo 外** ❓。

### 2.5 `scripts/etl/audit_done_details.py` / `scripts/export/export_silver_detail.py` ✅ 支援工具
- 前者：CH vs MSSQL Done 對帳；後者：Silver 明細匯出 Excel（`prd_audit/` 產物）。環境變數必填（已去 hardcode）。
- ⚠ memory-bank 提到的 `scripts/audit_all_lines.py` 在目前工作目錄不存在（可能已移除或未追蹤遺失）。

### 2.6 `sql/etl/dml/backfill_silver.sql`（187 行）✅ **業務規則的單一真相來源**
- `vx_type` 判定優先序：① NPE 廠區且非 `V2%` → V1；② MoNumber 前 3 碼 ∈ {196,199,200,210,212,213} → V1；③ `TASK_DEF_KEY_` 前綴 V1/V2/V3。（**不含 315**——已於 2026-07-06 決策維持現狀，見 Assessment §6.1）
- 五階維度 fallback 鏈：varinst 變數 → MDM 精確（line+plant）→ MDM plant 單鍵備援 → `''`（空字串，**不用 UNKNOWN**）。所有 MDM 欄位包 `NULLIF(x,'')`（CH LEFT JOIN 失敗回 `''` 非 NULL）。
- 排除規則（`is_excluded`/`exclude_reason`）：autoComplete=1（bypass）、`EmpName='SYSTEM'`（system_bypass）、`TASK_DEF_KEY_ LIKE 'E%'/'C%'`（system_node）、MoNumber `Q%`/`R%`（測試單）、任務名含 Notify/Dummy。
- Cohort 標籤：`status_daily/weekly/monthly`（開單日/ISO 週末/月底前完工判定）。
- varinst 關聯用 `argMax(欄位, _refresh_time) GROUP BY PROC_INST_ID_` 防 JOIN 翻倍。
- 尾部 `SETTINGS allow_experimental_analyzer = 0`（CH 25.8 analyzer bug workaround）。

### 2.7 Gold DML（✅ 均讀過）
- `backfill_gold_milestone.sql`：以 `groupBitmapStateIf(cityHash64(task_id), <日期條件>)` 產日/週/月三組 Todo/Doing/Done Bitmap 快照。**注意**：Cohort 條件是用 `task_claim_date`/`task_end_date` 內聯重新計算，**不是**讀 Silver 的 `status_daily/weekly/monthly` 欄位（那三欄目前只被 `cube_l5_task_details.js` 顯示用）——同一套 Cohort 邏輯存在兩處，修改時必須同步，否則明細與 KPI 口徑漂移 ⚠。
- `backfill_gold_acc.sql`：`ARRAY JOIN range(task_start_date, +7天)` 展開任務存續期 → 7 日滾動在途/總開單 Bitmap（`is_excluded=0`）。
- `backfill_gold.sql`：milestone + acc FULL OUTER JOIN → completion_phys。（**仍在用**，勿信舊 README 的「已棄用」）
- `backfill_gold_summary_historical.sql`：V3 混合（Day=事件日 ARRAY JOIN、Week/Month=Cohort、ISO 跨年週過濾 `toISOYear=toYear`）；只寫 `<2026-04-01`。
- `backfill_gold_summary.sql`：V4（從 completion_phys 的 Bitmap 轉整數）；只寫 `≥2026-04-01`；含「零開單日 acc 補丁」（LEFT ANTI JOIN 補假日佔位列）。
- 兩者邊界互斥，由 SQL 內 WHERE 硬編碼日期 `2026-04-01` 保護。**改動任何一側都要檢查邊界不重疊**。

### 2.8 Cube.js 模型（`cube/model/cubes/`）✅
| 檔案 | 讀取表 | 用途 | 狀態 |
|---|---|---|---|
| `cube_l5_task_periodic.js` | `gold.rmv_l5_task_summary FINAL` | KPI 寬表（7日+3週+當月，anchor_dt 時光機） | ✅ 生產 |
| `cube_l5_task_periodic_pivot.js` | 同上 | 長表/轉置版 | ✅ 生產 |
| `cube_l5_task_details.js` | `silver.mv_fact_task_vx FINAL` | 明細鑽取（含 status_* cohort 欄位顯示） | ✅ 生產 |
- 費率指標一律 `floor(qty*100/total)` 整數百分比（Rule 2：<1 最高 99%）。
- anchor_dt：取 filter 範圍內 `max(snapshot_date)`（不超過 today）作基準日。
- ❓ `staff_usage.js`（L7 人員使用率，讀 `gold.tb_active_user_metrics`）曾以 untracked 副本存在於本 repo，2026-07 清理未追蹤暫存檔時已移除（本來就非本 repo 追蹤內容）；正式檔案位置與現況需向使用者確認。

### 2.9 `api/main.py`（FastAPI，302 行）✅
- `GET/POST /api/l5/task-report`：輸入 month（yyyy-MM）+ 五階維度，輸出當月/最後 3 ISO 週/最後 7 天的指標矩陣。讀 `gold.rmv_l5_task_completion`（VIEW+FINAL）。port 7088→8000（`infra/api/docker-compose.yml`）。

### 2.10 Node BFF（reports.js，不在本 repo）❓
- 依 Troubleshooting C2 記載：Express router，簽發快取 JWT 呼叫 Cube.js REST（TTL 1h、到期前 5 分換新——修復跑超過 24h token 過期 bug）。實際部署在另一個前端專案；曾有 untracked 參考副本存於 `api/reports.js`，2026-07 清理未追蹤暫存檔時已移除。

### 2.11 infra/ ✅
- `infra/.env`（不進版控）：`CLICKHOUSE_HOST/PASSWORD`、`CUBEJS_API_SECRET` 等。
- `infra/cube/docker-compose.yml`：cubejs/cube:latest，`CUBEJS_DB_PORT=8121`，掛載 `cube/model`。
- `infra/api/docker-compose.yml`：python:3.10-slim 直跑 main.py。
- `infra/monitoring/docker-compose.yml`：Grafana(9003, SMTP deltarelay, ROOT_URL=Server 207) + Prometheus(9011) + node-exporter。Grafana「Bronze Sync Monitoring」dashboard 監控正式環境同步健康。
- `infra/clickhouse/`：config.d（併發保護 `max_concurrent_queries=50`⚠ 未逐檔驗證）、users.d、odbc/odbc.ini（DSN 定義）。

### 2.12 tests/ ✅（檔名層級）
`test_sync_odbc.py`、`test_execute_etl_oom.py`（OOM 切窗）、`test_etl_windows.py`（視窗生成）、`test_pipeline_config.py`（設定一致性）、`test_api_main.py`、`test_audit_script.py`。跑法：`python -m pytest tests/ -v`。⚠ 未實際執行驗證通過與否。

---

## 3. 模組重要度分級（AI 修改前必讀對照）

| 級別 | 模組 | 修改注意 |
|------|------|----------|
| 🔴 核心（動前先讀 KB+Guide） | `backfill_silver.sql`、`backfill_gold_summary*.sql`、`execute_etl.py`、`sync_unified_odbc.py`、`pipeline_config.yaml` | 影響 KPI 正確性；改 SQL 需考慮歷史回填與 V3/V4 邊界 |
| 🟠 生產服務 | cube 兩支 periodic 模型、`api/main.py`、`sync_tables.yaml`、schema DDL | 改 measure 需遵守 Rule 2 floor()；改 DDL 需 setup_schema 重佈 |
| 🟡 支援 | audit/export 腳本、monitoring compose、tests | 相對安全 |
| ⚪ 可忽略 | `archive/`、`prd_audit/`、`prd_mssql/`、`.kiro/specs/`、`scripts/performance/`、`docs/archive/` | 歷史封存/一次性產物，**不要**依其實作 |
