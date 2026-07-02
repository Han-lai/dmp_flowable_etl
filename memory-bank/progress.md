# 專案進度 (Progress)

## 項目概述
DMP Flowable L5 數據流水線遷移轉換，由 V2 (Silver DISTINCT) 升級至 V4.3 (Super Silver) 架構，旨在建立高品質、高精確度的統一任務事實表，達成 KPI 指標與 UI 明細的 100% 同步。

## 已完成里程碑 (Milestones)

### 2026-07-02: Bronze 同步 MSSQL_PASSWORD 事故根因修復確認

- **事故摘要**：每日排程（`sync_unified_odbc.py --table all`）的執行環境缺少 `MSSQL_PASSWORD` 環境變數，fallback 成空字串，ODBC bridge 以 `Pwd=;` 連 MSSQL 失敗（Code 86）。full 策略的 15 張維度表（`common_hr_employee`、`common_mdm_*` 等）每次 TRUNCATE 後 INSERT 失敗留空表，6/17、6/29、6/30 連續三天發生，每次靠人工手動補跑（`python sync_unified_odbc.py --table all` 帶正確環境變數）才恢復。
- **修復**：infra 在正確的排程器環境補上 `MSSQL_PASSWORD`（及 `CLICKHOUSE_HOST`、`CLICKHOUSE_PASSWORD`）。
- **驗證**：2026-07-02 00:00:11~00:00:34 自動排程首次成功完成，`bronze._sync_watermark` 所有 19 張表 `sync_time` 更新，full 策略表全部有資料。

---

### 2026-06-29~07-01: 安全性清洗、fail-loud 修復、Grafana 監控建置

**GitHub 機敏資訊清洗**：
- `git filter-repo` 清洗 192 commits 的完整歷史：移除 ClickHouse 真實密碼（`1qaz2wsx3edc`）、內部 IP（`10.146.206.76`、`10.136.218.207`）、`CUBEJS_API_SECRET` 舊密鑰（`dmp_flowable_cube_secret_key_2026`）
- 128 筆公司帳號 `albee.lai@deltaww.com` 的 author/committer 全數改寫為 `Han-lai <sh41bee@gmail.com>`
- Force-push 覆蓋 `github.com/Han-lai/dmp_flowable_etl` 的 `master` 與 `main` 分支
- ClickHouse 密碼已旋轉（新密碼存於 `infra/.env`，不進版控）；CUBEJS_API_SECRET 換新密鑰並改由 `infra/.env` 提供
- 全域規則寫入 `~/.claude/CLAUDE.md`：push GitHub 前一律禁止 IP/密碼出現，commit 用 Han-lai 身份

**程式碼環境變數化（工作目錄未 commit）**：
- `scripts/export/export_silver_detail.py` → `CH_HOST`/`CH_PASSWORD` 改為 `os.environ[...]` 必填
- `infra/api/docker-compose.yml` → `CLICKHOUSE_HOST`/`CLICKHOUSE_PASSWORD` 移除 IP/密碼 fallback
- `infra/cube/docker-compose.yml` → 同上，並補加 `env_file: ../.env`（原本寫死 IP，env_file 也缺失）
- `scripts/etl/init_pipeline.sh` → 改用 `${VAR:?must be set}` 強制檢查必填
- `claude.md` → 移除 IP 字串，改寫成「請見 `infra/.env`」
- `infra/monitoring/docker-compose.yml` → 同步成線上實際版本（Prometheus port 9011、scrape config 內嵌）

**`sync_unified_odbc.py` fail-loud 修復（工作目錄未 commit）**：
- `main()` 結尾加 `sys.exit(1)`（11 行），當任何表狀態 `!= "SUCCESS"` 時 exit 非零
- 修復「masking bug」：之前整批失敗仍 exit 0、排程顯示假成功，6/17 事故的直接元兇之一
- 已用 `identitylink` 表（batch 策略，不 TRUNCATE）在缺少 MSSQL_PASSWORD 情境下實測觸發成功

**Grafana Bronze Sync Monitoring（`http://10.136.218.207:9003`）**：
- 新增 ClickHouse datasource `grafana-clickhouse-datasource-76` 指向 `10.146.206.76:9000`（正式環境）
- 建立 Dashboard `Bronze Sync Monitoring (10.146.206.76)`，uid `afe90588-6fc1-494e-9b97-9a4d5e2b0cf6`，含 4 個 panel：
  1. **近 24h 失敗計數**（stat，紅/綠燈閾值）
  2. **失敗清單**（table，含 exception 完整文字）
  3. **7 天失敗趨勢**（timeseries，每小時 bucket）
  4. **表狀態總覽**：結合 `bronze._sync_watermark`（最後成功時間，快速查詢）+ `system.query_log`（最後失敗時間）；依 `sync_tables.yaml` 的 full/batch 策略分流：full 表用 `current_rows=0` → 🔴空表；batch 表只用 `hours_since_success>=24` → 🟠過期；兩者都正常 → ✅正常

---

### 2026-06-09: CH vs MSSQL 全線體對帳腳本建立與 vx_type 修正

- **對帳腳本 `scripts/audit_all_lines.py` 建立**: 支援 `--period`（Day/Week/Month）、`--vx-type`（V1/V2/V3）、`--start/--end`、`--diff-only`、`--csv`、`--factory/--line/--plant` 等參數，輸出含 `dt`（每日日期）欄位，CSV 含 status 分類（diff/ok/only_ch/only_ms）。
- **關鍵 Bug 修正：MSSQL vx_type 分類需複製 Silver 覆蓋規則**: 單純用 `TaskDefinitionKey LIKE 'V3%'` 會多算，因 Silver 有兩條覆蓋規則：(1) MoNumber 前三碼 IN ('196','199','200','210','212','213') → 強制 V1；(2) Factory='NPE' AND TaskDefinitionKey NOT LIKE 'V2%' → 強制 V1。SMT-S12 WJ2 案例：18,944 筆 TaskDefinitionKey=V3_xxx，但 CH Gold V3 只有 7,082 筆，差距來自 MoNumber 前綴覆蓋。
- **period_type 差異釐清**: Cube 顯示 Done=1328（Month cohort），腳本預設 Day cohort 得到 911，兩者均正確但口徑不同，加入 `--period` 參數讓使用者明確選擇。
- **2026-04-24~04-30 三版本對帳結果**:
  - V3（Day）: 71條OK / 14條差異，最大差距 -8 筆，Done% 全部吻合 → 同步邊界效應
  - V1（Day）: 1631 行輸出，6條差異
  - V2（Day）: CH 無 V2 資料（0筆），MSSQL 有 563 筆 → 該期間 V2 任務均被 Silver 歸入 V1
- **CSV 輸出**: 三份 CSV 保留於根目錄（diff_v3/v1/v2_daily_0424_0430.csv）

---

### 2026-06-05: Cube 費率指標 floor() 修復與 todoRate/doingRate 新增

- **費率規格 Rule 2 修復** (`8da3d57`): 將 `cube_l5_task_periodic.js` 與 `cube_l5_task_periodic_pivot.js` 中所有費率指標（doneRate, doingDoneRate, accRate, task_pct 系列）從 `round(..., 2) * 100` 改為 `floor(qty*100/total)`，結果以整數百分比呈現，value=1 → 100%，value<1 → 最高 99%。
- **todoRate / doingRate 補充** (`2080fdb`): 在 `L5TaskPeriodic` Cube 補充原缺少的兩項指標，原先由 BFF `Math.round()` 計算；改為 Cube 統一以 `floor()` 處理，符合 Rule 2 規格。

---

### 2026-06-04: ETL 執行錯誤修復、varinst lookback 延長與 backfill_silver 重構

- **varinst lookback 365 天與防空行覆寫** (`d8ade48`): `backfill_pivot.sql` 回溯天數從 180 延長至 365，覆蓋長流程任務。新增 `HAVING` 子句，排除全空資料列，避免以新的 `_refresh_time` 覆蓋正確舊資料。`backfill_silver.sql` 移除 `UNKNOWN` fallback，改以空字串取代無法解析的維度欄位。
- **無效 ClickHouse settings 移除** (`d0753e3`): 刪除 `execute_etl.py` 中導致執行錯誤的 2 個無效設定。
- **backfill_silver 共用 CTE 重構** (`ca465a7`): 以共用 CTE 架構整併重複邏輯（-13 行 / +10 行），同時保持 NULLIF region 修復效果。

---

### 2026-06-03: V2/V1 四階維度 region 修復與全量回填

**問題根因**: V2 任務只送 `varinst_plant`（DG3/WJ2），不送 `varinst_lineName`，導致精確 MDM JOIN 失敗。ClickHouse LEFT JOIN 失敗時 String 欄位回傳 `''` 而非 NULL，`COALESCE` 不跳過空字串，備援邏輯從未被執行。

**修復檔案**: `sql/etl/dml/backfill_silver.sql`
- 所有 `mdm.*` 欄位加上 `NULLIF(..., '')`，讓 JOIN 失敗的空字串轉為 NULL
- 移除 region 備援的 `IF(lineName IS NULL)` 條件，改為精確 MDM 查不到即啟用 plant 備援
- 四階回推設計邊界：`plant→factory` 為 1:N 不可回推，V2 的 factory 維持 UNKNOWN

**回填範圍**: 2025-10 至 2026-05，共 8 個月全部完成

**Gold 層清理**: 執行 `ALTER TABLE DELETE WHERE region = ''` 刪除四張 Gold 表的舊資料（共約 12,330 筆）

**驗證**: Silver `region=''` 筆數為 0，Gold 篩選 CNE/CNS 均有正確資料

---

### 2026-05-27 (下午): Phase 4 Cube 預聚合架構完成與 anchor_dt 全面遷移
- **Gold Summary 預聚合表上線**：新增 `gold.rmv_l5_task_summary` 整數彙總表，ETL 在寫入階段完成 bitmap merge，Cube 查詢只做 SUM，查詢耗時降至 0.06~0.11 秒。
- **L5TaskPeriodic & L5TaskPeriodicPivot 全面改寫**：兩個核心 Cube 完全捨棄即時 Bitmap 運算，改讀預聚合表，並將 anchor_dt 計算來源也遷移至 `rmv_l5_task_summary FINAL WHERE period_type='Day'`，兩個 Cube 現只讀一張表。
- **Cube 檔案整理**：刪除冗餘的 `cube_l5_task_summary.js`（邏輯已合併至 periodic）與 `cube_5level.js`（效能問題待重新設計）。
- **MSSQL 來源表版本升級**：`sync_tables.yaml` 全部從 `_0202`/`_0108` 升至 `_0503`。
- **GitLab 推送**：3 個 commits 已推送至 `master`（`6b9527e`, `56f3201`, `cb4275f`）。

### 2026-05-27: Watermark 結構升級、ETL 接龍自癒與正式資料庫無痛置換切換
- **正式環境無痛置換與遷移 (Production Switchover)**：成功將原本不帶後綴的舊正式資料庫（`bronze`, `silver`, `gold`, `ops_metrics`）改名，打包封存為 **`_0202`** 後綴（如 `bronze_0202`），作為歷史資料的安全存檔。接著重新建立全新標準正式庫，並將已在 `_0503` 測試沙盒驗證無誤的實體表瞬間搬移移入。
- **Views 視圖重新部署與 100% 驗證**：在新正式庫中重新部署 `sql/etl/schema` 目錄下的 9 個 DDL 檔案。經執行 `python scripts/etl/execute_etl.py --status` 驗證，正式環境的 `bronze.bpm_act_hi_taskinst` (674萬行)、`silver.mv_fact_task_vx` (698萬行) 與 `gold.rmv_l5_task_summary` (6.7萬行) **數據完全到位，正式版完美宣布上線！**
- **水位線真實時間跨度追蹤**：在 `bronze._sync_watermark` 水位線表成功擴充 `min_data_time` (資料最舊時間) 與 `max_data_time` (資料最新時間) 兩個 Nullable(DateTime64(3)) 欄位。自動在增量抽取成功後，查詢 ClickHouse 的真實時間 `MIN` 與 `MAX` 值並寫入，達成極低開銷的真實資料跨度監控。
- **無痛平滑結構升級**：在 `sync_unified_odbc.py` 中實作啟動時的 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 自動結構遷移，確保正式與沙盒環境能無痛自動升級而不影響現有數據。
- **智能 Auto-Catchup (自動接龍)**：升級 `execute_etl.py` 中的 `--daily` 模式，自動讀取 Checkpoint 的 `max(window_end)` 與 Watermark 邊界，全自動動態計算本次補算起迄點，不需手動指定。
- **空窗跳過與自我療癒 (Safe-Run)**：實作防 OOM 安全機制。在計算前若 Bronze 筆數為 0 則 `Skip` 且**不標記 SUCCESS** 到 Checkpoint。這保留了未來若有遲到資料同步進來時，系統自動補算的自癒能力。
- **測試雙向對稱性**：在 `sync_unified_odbc.py` 中新增 `--db-suffix` 命令行參數，使數據抽取端也支援帶有 `_0503` 的測試庫（例如 `bronze_0503`），與 ETL 引擎達成 100% 完美的測試一致性！
- **Pipeline 狀態儀表板優化**：重構 `execute_etl.py` 中的 `show_status`，解除儀表板筆數查詢表名的 hardcoding 改為從 `pipeline_config.yaml` 中動態讀取。並擴充 `--status` 監控儀表板，將同步進度與新增的真實最舊/最新時間完美整合展現。

### 2026-05-26: Phase 4 預聚合與增量視窗 Bug 修復
- **正式環境切換與回滾**: 成功將測試環境 (`_0503`) 的概念部署至正式環境，統一使用 `bronze.*` 作過渡目標表，並確保 `sync_tables.yaml` 與 `execute_etl.py` 的組態還原為 GitLab 標準版本。
- **增量 ETL 的時間視窗修復 (ACC 數據流失問題)**: 發現並修復了 `backfill_gold_summary.sql` 中的重大 Bug。在使用 10天 Incremental ETL 聚合 `Week` 與 `Month` 粒度時，引入動態時間擴展 `toStartOfWeek` 與 `toStartOfMonth`，確保 `ReplacingMergeTree` 永遠能獲取完整的週/月聚合，完美對齊前端動態時光機的 30 天聯集 (ACC) 邏輯。
- **歷史數據重算**: 透過自訂腳本將 66,026 筆歷史聚合資料回填完畢，恢復 ACC 數據準確度。

### 2026-05-25: Cube.js 語意層效能極限優化 (O(1) 架構重構)
- **破除全表掃描黑洞 (Filter Pushdown)**: 將 Cube Models 裡會導致 ClickHouse 放棄下推過濾條件的 `CROSS JOIN` 語法，全面替換為 `Constant Scalar WITH`，確保主鍵索引能發揮作用。
- **主鍵索引修復 (Index Fix)**: 移除了日期篩選條件的 `formatDateTime` 函數包裝，讓資料庫能以原生格式快速搜尋。
- **指標聚合優化 (Measure Optimization)**: 升級所有數量型指標，將 `bitmapCardinality(groupBitmapMergeState(x))` 精簡為更高效的原生函式 `groupBitmapMerge(x)`。
- **成果與發布**: 成功將時間與空間複雜度由 O(N²) 降維至 O(1)，使單一大範圍查詢從 30 秒 (超時) 降至 1.5 - 8 秒，並順利推送到 GitLab `master` 分支。

### 2026-05-18: 機房新伺服器 (<OLD_SERVER_HOST>) 部署與全量資料對帳
- **腳本連線大更新**: 將專案中所有核心 Python 腳本（連線設定）由舊主機全面安全移轉至新主機 `<OLD_SERVER_HOST>`，採用 `default/default` 憑證。
- **跨伺服器秒級資料搬移**: 利用 ClickHouse 遠端直連函式 `remote()`，成功將 **53,388,806 筆** 核心 Bronze 資料在 3 分鐘內高速轉入新資料庫，完美避開 MSSQL 來源端無索引引發的 ODBC 分批超時限制。
- **ETL 完整重算與業務對帳**: 完成 `silver` 及 `gold` 兩層 `--reset` 重建與 Backfill 計算，比對 WJ2 廠區 `2025-12-31` 的 Todo(9)、Doing(5)、Done(186) 指標，數據達成 **0 誤差對齊**，證明新伺服器隨時可投入正式生產！

### 2026-05-07: 累積負載率 (Acc Rate) 指標優化
- **滾動分母實作**: 在 Gold 層新增 `acc_total_task` 欄位，實作 7 日滾動總開單量計算，徹底解決週末或低開單量時 Acc Rate 超過 100% 的數據震盪問題。
- **維度感知 (Dimension-Aware) 邏輯**: 
    - **日維度**: 採 7 日滾動積壓邏輯。
    - **週/月維度**: 採週期結算 (Period-End Settlement) 邏輯，確保與 Done Rate 指標在同時間粒度下邏輯一致。
- **Cube.js 優化**: 修改 `accRate` 度量，利用 `any(granularity)` 實作動態公式切換，解決 SQL 聚合錯誤。
- **全量回填**: 完成 2025-01 至今的所有歷史數據重整，確保生產環境指標精確。

---

## 當前狀態項目 (Status)

| 模組 | 狀態 | 備註 |
| :--- | :--- | :--- |
| **正式庫置換上線** | ✅ 標準無後綴正式上線 | 已將舊庫封存為 _0202，並把驗證後的 0503 瞬間改名移入標準正式庫 |
| **Bronze Sync Watermark** | ✅ 欄位擴充與自動時間追蹤 | 已新增 min_data_time 與 max_data_time 並支援平滑遷移與對稱測試 |
| **Bronze Sync 排程穩定性** | ✅ MSSQL_PASSWORD 修復，2026-07-02 首次自動成功 | 事故：6/17、6/29、6/30 空密碼導致 15 張 full 表清空；已修復環境變數 |
| **Grafana 監控 Dashboard** | ✅ Bronze Sync Monitoring 建立 | 指向正式環境 .76，4 panels，full/batch 分流判斷狀態 |
| **sync_unified_odbc.py fail-loud** | ✅ sys.exit(1) patch（未 commit） | 修復靜默失敗 masking bug，已實測驗證 |
| **GitHub 安全性清洗** | ✅ 密碼/IP/身份全數清洗 | git filter-repo 清洗 192 commits，已 force-push |
| **ETL Catchup & Checkpoint** | ✅ 智能自動接龍與空窗自癒 | 支援 max(window_end) 接龍、空窗 Skip 與對稱測試 |
| **狀態儀表板 Dashboard** | ✅ show_status 動態優化 | 支援 YAML 動態掃描、最舊最新資料時間完美整合同步呈現 |
| **Silver Fact Layer** | ✅ V4.3 | 超級事實表 (Super Silver)，包含 L4、業務變數與時效 |
| **Gold Layer ETL** | ✅ V4.2 | 支援週期感知 (Period-Aware) 與多粒度 Bitmap |
| **DML 效能** | ✅ 已優化 | 實作 argMax 去重，確保 JOIN 後不產生重複數據 |
| **ETL 檔案清理** | ✅ 已完成 | 僅保留 `execute_etl.py` 與核心 SQL 模板 |
| **Cube.js Model** | ✅ V4.3 | 新增 `L5TaskDetailsSuper` 用於正式明細鑽取 |

## 待辦事項 (Todo)
- [x] 解決 W1 跨年數據對帳落差。
- [x] **將 UI 明細邏輯整合進核心 Fact Table (V4.3 升級)**。
- [x] **實作 DML argMax 去重優化，解決資料重複問題**。
- [x] **清理過時 ETL 程式碼與檔案**。
- [x] **升級 Watermark 水位線表結構，新增資料最舊/最新時間欄位 (2026-05-27)**。
- [x] **實作 ETL 智能自動接龍與防空窗 OOM 自我療癒機制 (2026-05-27)**。
- [x] **擴充 --status 監控儀表板，整合展示真實資料時間跨度 (2026-05-27)**。
- [x] **資料庫正式環境無痛置換遷移 (0503 -> 標準正式，舊正式 -> 0202) (2026-05-27)**。
- [x] 提交並推送所有 V4.3 邏輯變更至版本控制。
- [x] 修復 varinst lookback 365天、防空行覆寫 (2026-06-04)。
- [x] 移除無效 ClickHouse settings 修復執行錯誤 (2026-06-04)。
- [x] backfill_silver.sql 共用 CTE 重構 (2026-06-04)。
- [x] 費率指標統一改為 floor() 整數百分比，符合 Rule 2 規格 (2026-06-05)。
- [x] 新增 todoRate / doingRate 至 L5TaskPeriodic Cube (2026-06-05)。
- [x] GitHub 機敏資訊清洗（密碼/IP/作者身份）+ ClickHouse 密碼旋轉 (2026-06-29)
- [x] sync_unified_odbc.py fail-loud sys.exit(1) + 實測驗證 (2026-06-29)
- [x] Grafana Bronze Sync Monitoring dashboard 建立（4 panels）(2026-06-30)
- [x] MSSQL_PASSWORD 環境變數修復，自動排程 2026-07-02 首次成功 (2026-07-02)
- [ ] 觀察 Super Silver 表在前端 Superset 的明細鑽取效能。
- [ ] sync_full_table() TRUNCATE 無回滾結構性風險（改暫存表替換方案）
- [ ] 將工作目錄未 commit 修改推送至 GitLab
