# Troubleshooting Guide（事故史與踩坑錄）

**建立日期**: 2026-07-03｜**來源**: memory-bank、git log、程式碼註解交叉彙整（各條目附證據位置）
**用法**: 遇到症狀先搜本文；每條含根因與現行解法，避免重複踩坑。

---

## A. 同步層（MSSQL → Bronze）

### A1. 【重大事故】full 策略表全部變空表（2026-06-17/29/30 三次）✅
- **症狀**: `common_hr_employee`、`common_mdm_*` 等 15 張維度表 0 筆，下游維度全空。
- **根因**: 排程環境缺 `MSSQL_PASSWORD` → fallback 空字串 → ODBC `Pwd=;` 登入失敗（Code 86）→ TRUNCATE 已執行、INSERT 全失敗。舊版還 exit 0 假裝成功（masking bug）。
- **現行解法**: ① 排程環境已補環境變數（2026-07-02 驗證恢復）；② fail-loud `sys.exit(1)`（`sync_unified_odbc.py:518`）；③ Grafana Bronze Sync Monitoring 告警。
- **結構風險已收斂 ✅**: `sync_full()` 已改為**暫存表 + 原子替換**（建 `{target}_tmp_*` → INSERT → 驗證 row_count>0 → `RENAME TABLE` 原子換入 → 失敗自動 rollback 還原原表）。INSERT 或驗證失敗時原表完整保留、暫存表被清理，不再留空表（Assessment R2 已實作）。
- **緊急恢復**: 帶正確環境變數手動 `python scripts/etl/sync_unified_odbc.py --table all`。

### A2. Code: 1000 / Timeout 重試無效反而拖慢 ✅
- **根因**: Code 1000 涵蓋連線中斷與「Too many simultaneous queries」，重試 3 次只是多等 90 秒。
- **解法**（已實作）: OOM(241)/Timeout/1000 直接 raise → `sync_batch_adaptive` 對半切時間區間遞迴（下限 30 分鐘）。其他錯誤才重試（每次重建 client session 避開死鎖）。

### A3. ODBC 動態探測死鎖（架構起源）✅
- **根因**: MS-ODBC driver 對 varchar(max)/xml 欄位自動探測會死鎖。
- **解法**: `sync_tables.yaml` 每表**必填** `engine_ddl` 顯式 schema，建臨時 `ENGINE=ODBC` 表抽取。新增表時絕不可省略 engine_ddl。

### A4. 【重大事故／連線不穩根因】IMC06 stale connection pool（chronic 2026-03~07）✅
- **症狀**: 同步跑到一半批次開始失敗，錯誤訊息含 `IMC06` /「connection is broken and recovery is not possible」；每批 hang ~30s 才失敗。長期造成間歇性同步失敗，含 bronze `bpm_act_re_procdef` 資料遺失。
- **根因**: `clickhouse-odbc-bridge` 是長生命週期 subprocess，ClickHouse 只 spawn 一次、自己永不重啟。其內部連線池（每 DSN 最多 16 條）持有的 MSSQL 連線，會被 container→MSSQL 路徑上的**有狀態防火牆／網路 idle timeout 靜默 drop**；跨 ~24h 排程間隔後池內連線多半已死，重用就 hang ~30s 後 IMC06 失敗。**重試或對半切窗都無效**——這不是資料量或時序問題，只有清空 poisoned pool 才能救。
- **🔑 真正根因（2026-07-21 查明）**: 連線字串裡的 **`MARS_Connection=yes`**。MARS 啟用時 SQL Server 的 **connection resiliency（連線復原）會被停用**——這正是錯誤訊息中最關鍵那句「**No attempt was made to restore the connection**」的成因：驅動不是「嘗試復原失敗」，而是**根本沒嘗試**。長時間傳輸只要網路稍有波動，連線就被直接標記 unrecoverable。本腳本每條連線同時只跑一個查詢，**不需要 MARS**。
- **現行解法**:
  1. **關閉 MARS（最關鍵）**：`build_odbc_conn()` 改 `MARS_Connection=no`，換回連線復原能力。**實測效果（2026-07-21 varinst）**：改動後 IMC06 **完全消失**，錯誤性質從「致命、整個 session 中止」降級為「可重試／可 adaptive split 救回」，同一區間重跑最終 SUCCESS。
  2. **關閉 bridge 連線池**：`odbc_bridge_use_connection_pooling = 0`，讓壞死連線沒機會被重用。⚠ **必須從 `clickhouse_connect` 的 client `settings` 傳，寫在 SQL 尾端 SETTINGS 子句無效**（見 A5）。
  3. **排程前清池**：`daily_etl_wrapper.sh`（Step 0）與 `init_pipeline.sh`（pre-flight）在同步前 `docker exec clickhouse-server-odbc pkill -f clickhouse-odbc-bridge`。⚠ **手動單表跑 `sync_unified_odbc.py` 會繞過這步**——2026-07-21 的失敗就是這樣踩到的。
  4. **快速失敗不空轉**：`StaleOdbcConnectionError` + `is_stale_odbc_connection_error()` 偵測 IMC06 後即 raise、**不 retry、不 adaptive split**，並印 `STALE_ODBC_HINT`。注意這只**偵測**不**修復**，真正清池仍靠重啟 bridge。
- **❌ 已推翻的解法（勿再依賴）**: odbc.ini 的 `KeepAlive=30`/`KeepAliveInterval=1`。理由有二：(a) **repo 裡的 `infra/clickhouse/odbc/odbc.ini` 根本不是容器讀的那份**——compose 掛載的是 CH 主機上的 `${VOLUMES_ROOT}/clickhouse-odbc/odbc.ini`，改 repo 檔對運行中的容器**完全無效**；(b) 即使已於 2026-07-20 部署生效，2026-07-21 仍照樣發生 IMC06，證明 keepalive 單獨不足以根治。另有一說指 ODBC Driver 18 根本忽略 odbc.ini 的 KeepAlive（未證實）。若要做 TCP keepalive，應走 OS 層，且 ⚠ `net.ipv4.tcp_keepalive_*` 是 **per network namespace**——compose 用 bridge network 時，**宿主機 sysctl 不會傳進容器**，必須寫在 compose 的 `sysctls:` 區塊。
- **緊急恢復**: `docker exec clickhouse-server-odbc pkill -f clickhouse-odbc-bridge`，再重跑同步（新 bridge 會在首次 ODBC 查詢時自動 spawn，空池）。⚠ 此指令須在 **CH 主機（`CLICKHOUSE_HOST`，見 `infra/.env`）** 上執行——開發用的 Windows 機器沒有 docker。

### A5. ODBC 設定必須從 client settings 傳，SQL 尾端 SETTINGS 子句無效（2026-07-21）✅
- **症狀**: `sync_batch` 的 INSERT SQL 尾端已寫 `SETTINGS ... odbc_bridge_use_connection_pooling = 0`，但錯誤訊息中的 bridge URL 仍是 `http://127.0.0.1:9018/?use_connection_pooling=1&...`——設定沒生效。
- **根因**: 該 setting 沒有被套用到 ODBC 讀取的 context（推測與 `INSERT … SELECT` 的 settings 作用域有關，確切機制未證實）。設定名稱本身是對的（`system.settings` 查得到，預設 1）。
- **解法**: 改從 `clickhouse_connect` 的 client settings 傳，會變成 HTTP 查詢參數、必定套用整個請求：
  ```python
  CLICKHOUSE_CONFIG = { ..., "settings": {"odbc_bridge_use_connection_pooling": 0} }
  ```
- **驗證方式**: 用該 client 查 `SELECT value FROM system.settings WHERE name='odbc_bridge_use_connection_pooling'`，應回 `0`（2026-07-21 實測通過）。

### A6. Code 629 HTTP_RANGE_NOT_SATISFIABLE（bridge 傳輸中斷）⚠ 未解
- **症狀**: `Code: 629 ... Cannot read with range: [12582912, -] ... (HTTP_RANGE_NOT_SATISFIABLE)`。ClickHouse ↔ odbc-bridge 的 HTTP 傳輸在 **12 MiB（12×1024×1024）** 位置中斷，ClickHouse 嘗試用 Range 續傳但 bridge 不支援。
- **性質**: 與 IMC06 不同，**這個是可恢復的**——`sync_batch` 的重試或 `sync_batch_adaptive` 的對半切窗能救回。2026-07-21 varinst 62 批中出現 7 次（其中一批連 3 次重試全滅，切窗後成功），整體最終 SUCCESS。
- **現狀**: 尚未根治，靠既有重試/切窗機制吸收。觀察到集中在資料量較大的批次。待 `MARS=no + pooling=0` 完整組合實跑後再評估是否減少。

## B. 運算層（Silver / Gold ETL）

### B1. OOM 切窗曾造成 1 秒資料縫隙 ✅
- **根因**: 舊版切窗用 `mid-1s`，DateTime64 亞秒 timestamp 落在縫隙遺失。
- **解法**（已實作）: 兩半共用中點閉區間，重複列由 ReplacingMergeTree 去重（`execute_etl.py:281-290` 註解）。

### B2. V2/V1 任務 region 空字串、前端選不到廠區（2026-06-03）✅
- **三層根因**: ① CH LEFT JOIN 失敗回 `''` 非 NULL，COALESCE 不跳過；② 備援條件過嚴（限 lineName 為空才啟用 plant 備援）；③ Gold ORDER BY 含 region，`''` 與 `'CNE'` 是不同 key，OPTIMIZE 無法去重。
- **解法**: NULLIF 包所有 mdm 欄位 + 放寬備援 + Gold 層 `ALTER TABLE ... DELETE WHERE region=''` + 全量回填 2025-10~2026-05。
- **通則**: 修正會改變 ORDER BY 內欄位值的資料時，舊值列必須 DELETE，OPTIMIZE 沒用。
- **設計邊界**: plant→factory 是 1:N 不可回推（V2 factory 維持 UNKNOWN/空）；line_name 非唯一鍵不可單鍵回推 plant。

### B3. varinst 變數比任務早建 180+ 天 → 維度遺失（2026-06-04）✅
- **解法**: `backfill_pivot.sql` lookback 延長至 365 天 + `HAVING` 跳過全空列（防空行以較新 _refresh_time 覆蓋正確歷史資料）。

### B4. ClickHouse 25.8 analyzer bug ✅
- **症狀**: 複合 JOIN ON 條件被誤處理。
- **解法**: `backfill_silver.sql` 尾部 `SETTINGS allow_experimental_analyzer = 0`；JOIN ON 只放 join key，條件邏輯移到 SELECT 層。

### B5. 增量窗跨週/月 → Week/Month 聚合遺失前段歷史（2026-05-26）✅
- **解法**: summary SQL 聚合範圍動態擴張 `toStartOfWeek`/`toStartOfMonth`。改 summary 時必須保留。

### B6. 跨年 ISO 週污染（Dec 29-31 計入次年 W01）✅
- **解法**: historical summary 的 Week 粒度加 `toISOYear=toYear` 過濾。驗證基準: W51=502/31, W52=583/46, W01=12/5（total/acc）。

### B7. 無效 ClickHouse settings 導致執行錯誤（2026-06-04）✅
- 教訓: 對 25.8 加 session settings 前先在 clickhouse-client 驗證存在性。

### B8. bypass 同步缺口（2026-06-16，8 筆 CH_ONLY，未解）⚠
- **現象**: V3_5_1_10_6/7 後段步驟 autoComplete=1 但 BPM 主庫已清理 varinst，Bronze 抓不到，Silver 無法排除；assignee 為真人不能靠 SYSTEM 條件補救。
- **狀態**: 已知限制，對帳差異在可接受範圍（同步邊界效應）。對帳見到少量 CH_ONLY 先想到這條。

## C. 查詢/語意層（Cube.js / API）

### C1. 查詢 30~40 秒超時 → 0.06 秒的演進（效能問題定位順序）✅
1. 移除 `CROSS JOIN calc_anchor` → Constant Scalar WITH（filter pushdown）。
2. 移除被過濾欄位上的函數包裝（`formatDateTime` 會破壞主鍵索引命中）。
3. `bitmapCardinality(groupBitmapMergeState(x))` → `groupBitmapMerge(x)`。
4. 終極解: Phase 4 預聚合（summary 表，查詢只剩 SUM）。
- **通則**: Cube 慢先查 `system.query_log` 確認實際 SQL 打到哪張表、是否命中主鍵。

### C2. BFF 24 小時後全部 403 "jwt expired" ✅
- **根因**: reports.js 模組載入時只簽一次 1d token。
- **解法**（已實作）: token 快取 + 到期前 5 分鐘重簽（TTL 1h）。

### C3. 費率顯示不符規格（Rule 2）✅
- round() 會四捨五入到 100%；規格要求 <1 最高 99%。一律 `floor(qty*100/total)`。

### C4. anchor_dt 短暫落後 ⚠（已知風險，接受中）
- ETL 執行期間 summary 是最後階段，Cube 讀到的基準日可能落後數分鐘。

## D. 監控層（Grafana）

### D1. Dashboard 誤報/漏報三連坑（2026-07-03 調校）✅
- `ILIKE '%INSERT INTO bronze.%'`（前導 %）會把監控自身的 SELECT 計入失敗 → 改精確錨定 `ILIKE 'INSERT INTO bronze.%'`。
- INSERT 前有 `\n` 縮排使錨定失效（trim() 不去 \n）→ 改 `match()` regex。
- ClickHouse 不支援 CJK alias（`AS 失敗次數` 語法錯誤）→ 英文 alias + Grafana displayName override。
- `ExceptionBeforeStart` 的 `query_kind` 永遠 None，別用它篩選。
- 不重複表數: `uniq(extract(query, 'INSERT INTO (bronze\\.[a-z_]+)'))`，正常日凌晨=19。

### D2. 快速診斷 SQL
```sql
-- 各表最後同步狀態
SELECT table_name, row_count, sync_time FROM bronze._sync_watermark FINAL ORDER BY sync_time;
-- 近期同步失敗完整錯誤
SELECT event_time, substring(exception,1,400) FROM system.query_log
WHERE type='ExceptionBeforeStart' AND query ILIKE 'INSERT INTO bronze.%'
ORDER BY event_time DESC LIMIT 20;
```

## E. 對帳（CH vs MSSQL）判讀基準 ✅

| 差異型態 | 判讀 |
|---|---|
| PRD_ONLY 且 assignee=DMPV0001 | system_bypass 正確排除，非錯誤（2026-04 對帳 165 筆全屬此類） |
| CH_ONLY 少量（<10/線體）且 Done% 吻合 | 同步邊界效應或 done.csv 時間差，非資料錯誤 |
| CH_ONLY 且 autoComplete 任務 | 見 B8 bypass 同步缺口 |
| V2 期間 CH=0 但 MSSQL 有值 | 正常——被 Silver MoNumber/NPE 規則歸入 V1 |
| V3 計數 CH 遠低於 MSSQL | 檢查 MSSQL 查詢端是否複製了 Silver 覆蓋規則（教訓: 18,944 → 7,082） |
| Silver 筆數異常膨脹 | 跑 `OPTIMIZE TABLE ... FINAL` 清 stale rows（曾清 566 萬列）後再對 |
