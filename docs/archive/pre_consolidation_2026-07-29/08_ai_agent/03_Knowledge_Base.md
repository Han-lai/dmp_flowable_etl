# Technical Knowledge Base（技術知識庫與術語表）

**建立日期**: 2026-07-03｜**目的**: 解釋每項技術「為什麼存在」，讓小模型不必重新推導設計動機。

---

## 1. 技術選型與存在理由

### ClickHouse（v25.8，數倉本體）
- **為什麼**: 需要對千萬級任務列做多維聚合，MSSQL 生產庫不能承受分析負載。
- **互動模組**: 全部 ETL 腳本、Cube.js、FastAPI、Grafana。
- **本專案的特殊用法**:
  - **所有表都是 `ReplacingMergeTree`**：以「重複 INSERT + 背景去重」取代 UPDATE。去重鍵=ORDER BY，版本欄=引擎參數（bronze 用 `_sync_version`、silver 用 `_mview_update_time`、gold 用 `_refresh_time`、watermark 用 `sync_time`）。
  - **讀取需 `FINAL`（或容忍重複）**：查詢端（Cube/View/watermark 查詢）一律 FINAL；ETL 中間層靠 argMax 迴避 FINAL 成本。
  - **`ENGINE=ODBC` 代理表**：用顯式 schema 建臨時 ODBC 表抽 MSSQL，繞過自動型別探測在 varchar(max)/xml 欄位上的死鎖。
  - **Bitmap 聚合**（`groupBitmapState`/`groupBitmapMerge`/`bitmapCardinality`）：Gold 層以任務 ID bitmap 做跨維度去重計數；V4.3 起把 bitmap→整數轉換移到 ETL（summary 表），查詢端只剩 SUM。
- **已知地雷**: 見 [05_Troubleshooting.md](05_Troubleshooting.md)（LEFT JOIN 空字串、analyzer bug、CJK alias、ALTER DELETE vs OPTIMIZE…）。

### Medallion 三層架構（Bronze/Silver/Gold）
- **為什麼**: 來源是 EAV 型 BPM 資料（變數存在 `ACT_HI_VARINST` 的 name/value 列），必須先轉置才能當維度用；且 Server 76 記憶體有限，即時聚合會 OOM，所以每層物理化。
- **判斷方式**: 資料錯了往上游查——Gold 錯先看 Silver 該任務列，Silver 錯看 Bronze 原始列，Bronze 錯看 MSSQL 與 watermark。

### 時間視窗批次 + Checkpoint（自製微框架，無 Airflow）
- **為什麼**: 6GiB 可用記憶體跑不動全量，一切運算切成 7~15 天窗逐窗執行；`ops_metrics.etl_checkpoint`（phase × window_start × window_end → status）提供斷點續傳與防重跑。
- **注意**: SQL 模板佔位符是**字串替換**（`{start_ts}`/`{end_ts}`/`{start_date}`/`{end_date}`），不是參數化查詢——模板內不要出現字面 `{start_ts}` 以外的大括號變數。
- **自癒設計**: 空窗跳過但不標 SUCCESS → 遲到資料下次自動補算。

### Cube.js（語意層閘道）
- **為什麼**: 高併發（100 人）直連 CH 會 OOM；Cube 提供 SQL 翻譯、查詢合併、結果快取，把 DB 負載降 98%。**前端一律不准直連 ClickHouse**。
- **依賴它的**: Node BFF（不在本 repo）、Superset、BI Dashboard。
- **模型語言**: JS cube 定義，`FILTER_PARAMS` 下推過濾條件到內層 SQL（filter pushdown 是效能關鍵，勿把 filter 移出內層）。

### FastAPI / Node BFF / Spring Boot
- FastAPI：給後端程式對接的簡單 REST（讀 Gold View）。Node：Auth + 路由轉發 + 呼叫 Cube。Spring Boot：業務 CRUD（❓ 不在本 repo，僅架構圖提及）。

### Grafana + Prometheus（Server 207）
- **為什麼**: 2026-06 同步事故暴露「靜默失敗」，建立 Bronze Sync Monitoring（4 panels：24h 失敗數/失敗清單/7 天雙線趨勢/表狀態總覽）+ 郵件告警（SMTP deltarelay）。
- 判斷邏輯:full 策略表看 `current_rows=0`，batch 策略表看 `hours_since_success>=24`。

---

## 2. 核心業務術語表（Glossary）

| 術語 | 定義 | 出處 |
|------|------|------|
| **L5 任務完成率** | 核心 KPI：以五階維度統計任務 Total/Todo/Doing/Done 數量與比率 | `docs/03_metrics/01_Metrics_and_Data_Definitions.md` |
| **五階維度** | Region → Plant → Factory → Line（+ vx_type），源自 MDM 主檔與流程變數 | `silver.mv_dim_mfg_five_level` |
| **vx_type（V1/V2/V3）** | 業務流程版本歸屬。判定規則見 `backfill_silver.sql`（NPE→V1 最優先、MoNumber 前綴 6 組→V1、再看 TASK_DEF_KEY_ 前綴） | Code Intelligence §2.6 |
| **NPE 規則** | NPE 廠區的 `V3_` 任務強制歸 V1（V2 出貨行政任務除外），2026-06-08 加入 | `backfill_silver.sql:71-73` |
| **Cohort（梯次結算）** | 任務按「開單日」錨定（task_primary_date），狀態在日/週/月期末評估（status_daily/weekly/monthly），避免跨期重複計數 | `backfill_silver.sql` [C] 段 |
| **ACC（累積在途量）** | Day 粒度=7 日滾動視窗內未完成任務去重數（`rmv_l5_acc_phys` bitmap）；Week/Month 粒度=cohort 語意的 todo+doing | `backfill_gold_acc.sql`、summary SQL |
| **acc_total_task** | ACC 比率的分母：7 日滾動總開單量（解決週末分母過小使比率>100% 的問題，2026-05-07） | systemPatterns §6 |
| **Rule 2** | 費率顯示規格：整數百分比、無條件捨去 `floor(qty*100/total)`，值<1 最高顯示 99% | cube 兩支 periodic 模型 |
| **anchor_dt（時光機）** | Cube 查詢基準日=filter 範圍內 max(snapshot_date)（≤today），讓使用者可回看任意歷史日的「當時視角」 | `cube_l5_task_periodic.js` |
| **Watermark（水位線）** | `bronze._sync_watermark`：每表最後同步時間、累計筆數、真實資料 min/max 時間 | `sync_unified_odbc.py` |
| **Checkpoint** | `ops_metrics.etl_checkpoint`：ETL phase×時間窗的成功/失敗記錄，斷點續傳依據 | `execute_etl.py` |
| **Super Silver（V4.3）** | 2026-04-29 起 KPI 與 UI 明細共用單一事實表 `mv_fact_task_vx`（41 欄），單一真相來源 | systemPatterns §1 |
| **V3/V4 雙管線** | Gold summary 依 2026-04-01 硬邊界分流：舊資料用 V3 邏輯（事件日/cohort 混合）、新資料用 V4 Cohort bitmap | 兩支 summary SQL 檔頭 |
| **is_excluded / exclude_reason** | KPI 排除旗標：bypass、system_bypass（SYSTEM 帳號）、system_node（E%/C%）、Q/R 測試單、Notify/Dummy | `backfill_silver.sql` [E] 段 |
| **_0503 後綴** | MSSQL 來源表的版本快照後綴（歷經 _0108→_0202→_0503），由 DBA 更版，改版時只需改 `sync_tables.yaml` 的 source | sync_tables.yaml |
| **Server 76 / Server 207** | 76=正式 ClickHouse（Docker 11GiB）；207=舊伺服器，現跑 Grafana/Prometheus 監控與另一 CH 實例 | Architecture_Overview §6 |
| **L7 人員使用率** | 進行中的第二 KPI，量測授權人員的活躍率，來源表 `gold.tb_active_user_metrics` | ❓ 未完成，對應 cube 檔案現況待確認 |

---

## 3. 關鍵 ClickHouse 模式（複製即用）

### argMax 去重關聯（取代 FINAL 的高效模式）
```sql
SELECT PROC_INST_ID_, argMax(varinst_region, _refresh_time) AS varinst_region
FROM silver.mv_varinst_pivoted
WHERE PROC_INST_ID_ IN (...)   -- 一定要先縮小範圍
GROUP BY PROC_INST_ID_
```
用途：JOIN ReplacingMergeTree 未合併資料時防列數翻倍。

### NULLIF 空字串防禦（CH LEFT JOIN 特性）
```sql
COALESCE(NULLIF(v.region,''), NULLIF(mdm.region_code,''), NULLIF(mdm_plant.region_code,''), '')
```
原因：CH LEFT JOIN 失敗時 String 欄回 `''` 不是 NULL，COALESCE 不會跳過。

### 增量寫入慣例
每支 DML 都是 `INSERT INTO ... SELECT ... WHERE 時間 ∈ [{start_ts},{end_ts}]`，重跑靠 ReplacingMergeTree 去重（版本欄=now()），**去重鍵（ORDER BY）沒含的欄位改值時會產生殭屍列**——例如 gold 表 ORDER BY 含 region，region 由 '' 修正為 'CNE' 時舊列須 `ALTER TABLE ... DELETE WHERE region=''`（OPTIMIZE 無效，2026-06-03 事件）。

### 週/月聚合的視窗擴張
增量窗跨週/月邊界時，聚合範圍要擴張到 `toStartOfWeek`/`toStartOfMonth`，否則會遺失期間前段資料（2026-05-26 修復）。改 summary SQL 時必須保留此邏輯。

### 低記憶體 session settings（execute_etl.py --low-ram）
`max_threads=1`、`max_memory_usage=10e9`、`max_bytes_before_external_group_by/sort=500MB`、`join_algorithm='grace_hash'`、`max_bytes_in_join=500MB`。新增重查詢時比照。

---

## 4. 環境與連線（機敏值一律在 `infra/.env`，不進版控）

| 變數 | 用途 | 缺失後果 |
|------|------|----------|
| `CLICKHOUSE_HOST/PORT/USERNAME/PASSWORD` | 所有 Python 腳本與容器 | 連線失敗（腳本 fallback localhost） |
| `MSSQL_PASSWORD` | ODBC 連線字串 `Pwd=` | **fallback 空字串 → full 表 TRUNCATE 後全空**（6 月三次事故根因）。跑 sync 前務必確認存在 |
| `MSSQL_USER` / `ODBC_DSN` | 預設 `APP_SRV_BPM` / `MSSQL_DSN` | — |
| `CUBEJS_API_SECRET` | Cube JWT 簽發 | BFF 403 |
| `VOLUMES_ROOT` | api compose 掛載根 | 容器起不來 |

Port 對照（✅ compose 驗證）：Cube 4002/4003、FastAPI 7088、Grafana 9003、Prometheus 9011、CH HTTP 8123（腳本預設）/8121（cube 與 init_pipeline 預設）❓兩者對應關係依 `infra/.env` 實際值。
