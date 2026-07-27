# 當前工作脈絡 (Active Context)

**最後更新**: 2026-07-06

---

## 🎯 當前焦點 (Current Focus)

### ✅ 近期已解決 (2026-07-06 專案清理：暫存檔 + 壞測試 + 死碼 SQL)

- **未追蹤暫存內容清理**：刪除 `logs/output/`（16 個一次性除錯輸出）、`archive/`（25 個 V4 開發封存檔）、`prd_mssql/`（8 檔，含 527MB `done.csv`）、`.pytest_cache/`、多個 `__pycache__/`、`.deltacoder/`、以及未追蹤的 `api/reports.js`、`cube/model/cubes/staff_usage.js`（皆非 git 追蹤內容，刪除不影響版本歷史）。
- **恢復誤刪檔案**：`README.md`、2 個 pptx、`requirements-dev.txt` 原本已在工作目錄被刪除（非本次或前次 session 所為，原因不明），已 `git checkout` 恢復。
- **README.md 全面改寫**：修正失真連結、雙管線 Gold Summary 敘述、虛構的專案結構（舊版寫的 `api/routers/`、`cube/conf/`、`sql/queries/` 皆不存在），改為自足內容（不導向其他文件），新增「核心業務規則摘要」章節。
- **修復 2 支壞掉的單元測試**（跑 `pytest tests/ -v` 驗證，11 個測試全綠）：
  - `test_etl_windows.py`：原本 import 不存在的 `generate_windows()` 導致無法收集 → 在 `execute_etl.py` 把內嵌的視窗生成邏輯抽成獨立函數（純重構，逐行核對數學結果與原邏輯一致，無行為變動），與 `sync_unified_odbc.py` 的 `generate_batches()` 風格對稱。
  - `test_audit_script.py`：斷言還在檢查舊的字串拼接 SQL，但 commit `9e56480` 已把 `audit_done_details.py` 改成 ClickHouse 參數化查詢（防 SQL injection）→ 改斷言驗證正確行為（佔位符進 SQL、實際值進 `parameters` 字典）。
  - 環境問題：`venv/` 缺 `pytest`/`fastapi`/`pandas` 等 `requirements-dev.txt` 套件，`.venv/` 損毀（缺 `pyvenv.cfg`）；已在 `venv/` 補裝套件使測試可跑，但代表 clean checkout 後照 README 步驟會直接卡住，需要文件補一句「先 `pip install -r requirements-dev.txt`」。
- **刪除 4 個死碼/重複 SQL 檔案**（git rm，已 staged 未 commit）：
  - `sql/etl/schema/05_silver_dim_users.sql`、`sql/etl/schema/07_gold_kpi_user_utilization.sql`：整檔內容 100% 是註解的空殼 DDL，且引用已棄用的表名 `gold.rmv_user_utilization`（L7 現行方向已改走 `gold.tb_active_user_metrics`）。
  - `sql/setup/00_init_databases.sql`：與 `setup_schema.py` 的 `initialize_databases()` 完全重複，且未被任何腳本引用。
  - `sql/verification/06_validation.sql`：未被任何腳本引用，查詢已不存在的物件（`gold.rmv_user_utilization`、`system.view_refreshes` 對應已棄用的 Refreshable MV 架構、寫死日期的舊備份表）。
  - 已同步清理 `infra_config.yaml` 中對應的註解殘留引用。

### ✅ 近期已解決 (2026-07-03 AI 知識庫建立 — Fable 5 Intelligence Session)

- **新增 `docs/08_ai_agent/` AI 知識庫（8 檔）**：00 入口地圖、01 風險評估（含文件失真清單）、02 已驗證模組地圖、03 技術 KB + 術語表、04 開發規範、05 事故踩坑錄、06 AI 工作流程、07 交接補充。
- **新根目錄 `CLAUDE.md`**：取代已刪除的過時版本（舊版引用不存在的腳本），內含鐵律 + 導航 + 關鍵事實速記。
- **修正失真的 `sql/etl/dml/README.md`**：對齊 pipeline_config.yaml 的 8-phase 實況（舊版引用不存在的 sync_gold_unified.sql、誤標 backfill_gold.sql 已棄用）。
- **重要發現**：
  1. 🔴 5 個已 commit 檔案含內部 IP（memory-bank 三檔、grafana_dashboard_setup.md、monitoring compose），progress.md 另含已退役 CH 舊密碼 → **push GitHub 前必須清洗**。
  2. ✅ 315 工單規則不一致已決策（2026-07-06）：查證 Silver 表 mo_number 前綴 315 共 69 萬筆（88.5% 現為 V3），套用 `.kiro` spec 要求會造成大規模重新分類；配合變更記錄「315% 規則會致跨流程誤判」的既有結論，**維持現狀不套用**，該 spec 視為過時。已修正 `systemPatterns.md` 的錯誤記錄。
  3. ⚠ Cohort 結算邏輯雙處維護：silver status_* 欄位（明細用）與 gold milestone 內聯條件（KPI 用）非共用，修改需同步。

### ✅ 近期已解決 (2026-07-02 Bronze 同步 MSSQL_PASSWORD 事故根因修復確認)

- **事故根因修復確認**：`sync_unified_odbc.py` 每日排程因執行環境缺少 `MSSQL_PASSWORD`，導致 ODBC 以空密碼連線 MSSQL 失敗。`full` 策略 15 張表在 TRUNCATE 後 INSERT 失敗留空表（6/17、6/29、6/30 連續發生）。infra 補上環境變數後，**2026-07-02 00:00 首次成功完成自動排程**，所有表均同步正常。
- **驗證方式**：`bronze._sync_watermark` 所有表 `sync_time` 更新至 `2026-07-02 00:00:xx`，full 策略表 `current_rows` 均恢復非零。

### ✅ 近期已解決 (2026-06-29~07-02 安全性清洗與監控建置)

**GitHub 機敏資訊清洗**：
- `git filter-repo` 清洗歷史：移除 ClickHouse 密碼、內部 IP（正式 CH 主機、監控主機）、CUBEJS_API_SECRET 舊密鑰
- 192 個 commit 作者從 `albee.lai@deltaww.com` 改為 `Han-lai <sh41bee@gmail.com>`，force-push 至 `origin/master`
- ClickHouse 密碼已旋轉，CUBEJS_API_SECRET 已換新密鑰並改用環境變數（`infra/.env`）
- 程式碼環境變數化：5 個追蹤檔案移除寫死 IP/密碼（未 commit，留在工作目錄）

**`sync_unified_odbc.py` fail-loud 機制（未 commit）**：
- `main()` 結尾新增 `sys.exit(1)`，任何表失敗即讓排程真正回報失敗，修復「靜默失敗」bug
- 搭配 `daily_etl_wrapper.sh` 的 `set -e` 生效，已實測驗證

**Grafana Bronze Sync 監控 Dashboard（2026-07-03 完成調校）**：
- 新增 datasource 指向正式環境 `<CLICKHOUSE_HOST>:9000`
- `GF_SERVER_ROOT_URL=http://<MONITOR_HOST>:9003` 補入 docker-compose，告警郵件連結可點擊
- Dashboard「Bronze Sync Monitoring」含 4 個 panel（version 15）：
  1. **近 24h 失敗計數**：filter 精確錨定至 `ILIKE 'INSERT INTO bronze.%'`（不加前導 `%`，避免 SELECT 型監控查詢誤計）
  2. **失敗清單**：移除 `query_kind`（ExceptionBeforeStart 永遠是 None），同精確 filter
  3. **7 天趨勢（雙線）**：A=失敗次數（紅）/ B=成功同步表數（綠）。B 使用 `match()` regex + `uniq(extract(...))` 正確計算「不重複表數」，`match()` 解決 INSERT 前有 `\n` 縮排導致 ILIKE 錨定失效的問題；每次正常同步凌晨顯示 19 張
  4. **表狀態總覽**：full/batch 策略分流，full 看 `current_rows=0`，batch 看 `hours_since_success>=24`
- `hours_since_success`：距上次成功同步的小時數；< 24 = 正常，>= 24 = 🟠逾期
- 告警規則：A→B(reduce)→C(threshold) 結構，`error_type` label 動態帶入郵件主旨與內文，SMTP via deltarelay.deltaww.com:25

### ✅ 近期已解決 (2026-06-09 CH vs MSSQL 全線體對帳腳本)

- **`scripts/audit_all_lines.py` 正式完成**: 支援 `--period`、`--vx-type`、`--start/--end`、`--diff-only`、`--csv`，每列包含 `dt` 日期欄位，可直接匯出 Excel 日期篩選。
- **關鍵發現 — vx_type 查詢必須複製 Silver 覆蓋規則**: 不能只用 `TaskDefinitionKey LIKE 'V3%'`；需先排除 MoNumber 前三碼 IN ('196','199','200','210','212','213') 和 NPE factory 覆蓋，否則 V3 計數會虛高（SMT-S12 WJ2：18,944 → 7,082）。
- **V3 2026-04-24~04-30 對帳結論**: 14 條差異線體，最大 -8 筆，Done% 全部吻合，為同步邊界效應，非資料錯誤。
- **V2 期間空資料**: CH Gold V2 在此期間為 0，MSSQL 仍有 563 筆，正常（被 Silver NPE/MoNumber 規則歸入 V1）。

### ✅ 近期已解決 (2026-05-27 Phase 4 Cube 預聚合架構完成與 anchor_dt 全面遷移)
- **Phase 4 預聚合架構正式上線**：
    - 新增 `sql/etl/schema/06b_gold_kpi_task_summary.sql` 與 `sql/etl/dml/backfill_gold_summary.sql`，建立 `gold.rmv_l5_task_summary` 預計算整數彙總表。
    - 完全捨棄 Cube.js 語意層的即時 Bitmap 運算，改為直接讀取預聚合整數，查詢耗時從 ~750ms 降至 **0.06~0.11 秒**。
    - 改寫 `L5TaskPeriodic` 與 `L5TaskPeriodicPivot` 兩個 Cube，Measures 全面從 `groupBitmapMerge` 改為 `SUM`。
- **anchor_dt 全面遷移**：
    - 將兩個 Cube 的基準日計算（anchor_dt）從 `rmv_l5_task_completion_phys` 遷移至 `rmv_l5_task_summary FINAL WHERE period_type='Day'`。
    - 兩個 Cube 現在**只讀一張表** (`gold.rmv_l5_task_summary`)，完全移除對 `rmv_l5_task_completion_phys` 的依賴。
    - 已知風險：ETL 執行期間 summary 為 pipeline 最後階段，有短暫的資料落後視窗，目前接受此風險。
- **Cube 檔案整理**：
    - 刪除 `cube_l5_task_summary.js`（邏輯已合併至 `cube_l5_task_periodic.js`）。
    - 刪除 `cube_5level.js`（效能問題，原因：`leftUTF8()` 包裝導致全表掃描，待重新設計）。
- **ETL 來源表版本升級**：
    - `sync_tables.yaml` 所有 MSSQL 來源表從 `_0202`/`_0108` 更新為 `_0503`。
- **ClickHouse Log 驗證**：
    - 透過 `system.query_log` 確認 Cube API 查詢正確打到 `rmv_l5_task_summary`，效能穩定。
- **GitLab 推送 (3 commits)**：
    - `6b9527e` chore(etl): upgrade MSSQL source table versions to 0503 and improve scripts
    - `56f3201` feat(cube): replace live bitmap operations with ETL pre-aggregated Gold summary table
    - `cb4275f` refactor(cube): migrate anchor_dt to read from rmv_l5_task_summary

### ✅ 近期已解決 (2026-05-27 Watermark 結構升級與 ETL 自動接龍自癒機制)
- **正式環境無痛置換與遷移完成 (Production Switchover)**：
    - 成功執行資料庫置換更名。將原有的舊正式庫安全改名封存為 `_0202` 後綴（如 `bronze_0202`）。
    - 將已在 `_0503` 測試沙盒中完整驗證的實體數據表，瞬間無損地 `RENAME` 搬移移入全新的標準無後綴正式資料庫。
    - 成功重新部署 `sql/etl/schema` 下的 9 個核心 DDL schema 視圖，最後 `DROP` 刪除 `_0503` 空殼庫，實現秒級的正式環境安全上線！
- **水位線「真實資料時間跨度」自動追蹤**：
    - 升級 `bronze._sync_watermark` 表，新增 `min_data_time` (資料最舊時間) 與 `max_data_time` (資料最新時間) 兩個 Nullable(DateTime64(3)) 欄位。
    - 在每次同步後，自動查詢 ClickHouse 當前表的真實時間 `MIN` 與 `MAX` 值並寫入水位線表，達成超低開銷的真實資料跨度監控，免去每次掃描千萬筆大表的開銷。
- **無痛平滑遷移 (Auto Migration)**：
    - 在 `sync_unified_odbc.py` 中實作自動檢測與 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 機制。不影響現有資料，正式與沙盒環境皆能在下一次同步啟動時完成自動化結構升級。
- **智能 Auto-Catchup (自動接龍)**：
    - 升級 `execute_etl.py` 中的 `--daily` 模式，自動讀取 Checkpoint 的 `max(window_end)` 與 Watermark 邊界，全自動動態計算本次補算起迄點，不需手動指定。
- **空窗跳過與自我療癒 (Safe-Run)**：
    - 實作防 OOM 安全機制。在計算前若 Bronze 筆數為 0 則 `Skip` 且**不標記 SUCCESS** 到 Checkpoint。這保留了未來若有遲到資料同步進來時，系統自動補算的自癒能力。
- **測試雙向對稱性**：
    - 在 `sync_unified_odbc.py` 中新增 `--db-suffix` 命令行參數。這使數據抽取端也支援帶有 `_0503` 的測試庫（例如 `bronze_0503`），與 ETL 引擎達成 100% 完美的測試一致性！
- **Pipeline 狀態儀表板優化**：
    - 重構 `execute_etl.py` 中的 `show_status`，解除儀表板筆數查詢表名的 hardcoding 改為從 `pipeline_config.yaml` 中動態讀取。
    - 擴充 `--status` 監控儀表板，將同步進度與新增的真實最舊/最新時間完美整合展現。
- **代碼健康度重構**：
    - 消除變數遮蔽，修復 Bare Excepts，程式碼體質更為強健。

### ✅ 近期已解決 (2026-05-26 Phase 4 預聚合與增量視窗 Bug 修復)
- **正式環境切換與回滾**:
    - 成功將測試環境 (`_0503`) 的概念部署至正式環境，統一使用 `bronze.*` 作為目標表，並確保 `sync_tables.yaml` 與 `execute_etl.py` 的組態還原為 GitLab 標準版本。
- **增量 ETL 的時間視窗修復 (ACC 數據流失問題)**:
    - 發現並修復了 `backfill_gold_summary.sql` 中的重大 Bug：在使用 10 天 Incremental ETL 聚合 `Week` 與 `Month` 粒度時，原本會丟失當月前段的歷史資料。
    - **修復方案**：引入動態時間擴展 `toStartOfWeek` 與 `toStartOfMonth`，確保 `ReplacingMergeTree` 永遠能獲取完整的週/月聚合，完美對齊前端動態時光機的 30 天聯集 (ACC) 邏輯。
    - 成功透過自訂 Python 腳本將 66,026 筆歷史聚合資料回填完畢。

### ✅ 近期已解決 (2026-05-25 Cube 查詢效能極限優化)
- **破除全表掃描黑洞 (Filter Pushdown)**:
    - 移除了 Cube Models (`cube_l5_task_periodic.js`, `cube_l5_task_periodic_pivot.js`) 中舊有的 `CROSS JOIN calc_anchor`。改用 ClickHouse 高效的 `Constant Scalar WITH` 語法，成功讓廠區與日期條件下推至底層 ReplacingMergeTree。
- **主鍵索引修復 (Index Fix)**:
    - 移除了篩選條件上的 `formatDateTime` 函數包裝，確保資料庫能直接命中 Primary Key。
- **指標聚合優化 (Measure Optimization)**:
    - 將 `bitmapCardinality(groupBitmapMergeState(x))` 改為原生 `groupBitmapMerge(x)`，降低內部函數調用開銷。
- **效能驗證**:
    - 單一指標查詢由 30~40 秒 (引發 Timeout) 降至 **1.5 秒 ~ 8.5 秒** 的極速。時間與空間複雜度從 O(N²) 降為 O(1)。
    - 已將更新推送到 GitLab `master` 分支。

### ✅ 近期已解決 (2026-05-18 機房新伺服器部署與全量資料對帳)
- **新伺服器連線配置切換**:
    - 將 `setup_schema.py`、`execute_etl.py`、`sync_unified_odbc.py`、`audit_done_details.py` 的預設連線資料庫全部改為新環境 `<OLD_SERVER_HOST> (default / default)`。
- **跨伺服器秒級資料遷移 (Cross-Server Streaming)**:
    - 由於 MSSQL 生產端無索引導致 ODBC 增量同步超時，改採 ClickHouse `remote()` 原生串流技術，在 3 分鐘內將 **5,300 萬筆原始 Bronze 資料** 無損遷移至新伺服器！
- **Silver/Gold 全量重算與 100% 對帳**:
    - 以 `--reset` 方式徹底清空並重建新環境，重算後進行業務對帳。
    - **對帳結果 100% 一致**：WJ2 WJ-S28 線在 `2025-12-31` 的日結算數值與手冊文件精確契合（Todo: 9, Doing: 5, Done: 186, Total: 200）。

### ✅ 近期已解決 (2026-05-07 Acc Rate 指標優化)
- **積壓率分母優化 (7-Day Rolling Denominator)**:
    - 將日維度的 Acc Rate 分母從「單日總量」改為「7日滾動總量 (`acc_total_task`)」。
    - 解決了週末或開單量低時比率破表（如 460%）的問題。
- **維度感知指標 (Dimension-Aware Measures)**:
    - 在 Cube.js 中實作動態公式，自動切換日（滾動）與週/月（週期結算）的算法。
- **全量數據校準**:
    - 完成 2025-01 至今的全量回填，數據精確反映產線負擔。

### ✅ 近期已解決 (2026-04-29 V4.3 "Super Silver" 大統一與架構優化)
- **核心事實表大統一 (Consolidated Fact Table)**: 
    - 成功將「UI 明細層 V2」的強大功能完整整合進核心 `silver.mv_fact_task_vx`。
    - **不再區分 KPI 表與明細表**，達成「單一真相來源 (SSOT)」。
- **業務維度全覆蓋**: 
    - 新增 L4 流程定義、11 個業務變數（機種、工單、排程等）以及精確的分鐘級時效指標。
    - 修正了 **315** 工單分類邏輯，確保售後工單歸位。
- **DML 效能優化**: 
    - 實作了 `argMax` 去重關聯邏輯，解決了 `LEFT JOIN` 導致的資料虛胖問題，數據精度達成 100%。
- **全量回填與清理**: 
    - 完成 2025-09 至 2026-01 的全量歷史回填（對帳完全吻合：12/30 = 251, 12/31 = 200）。
    - 清理了所有過時的測試 DML 與 Schema 檔案。

### ✅ 近期已解決 (2026-06-05 Cube 費率指標 floor() 修復與 todoRate/doingRate 新增)

- **費率指標截斷規則修正** (`8da3d57`):
    - 將 `cube_l5_task_periodic.js` 與 `cube_l5_task_periodic_pivot.js` 中所有費率指標 (`doneRate`, `doingDoneRate`, `accRate`, 所有 `task_pct`) 從 `round(..., 2) * 100` 改為 `floor(qty*100/total)`。
    - 符合規格 Rule 2：值=1 顯示 100%，值<1 最高 99%，百分比以整數呈現（無小數點）。
- **新增 todoRate / doingRate 指標** (`2080fdb`):
    - 在 `L5TaskPeriodic` Cube 補充缺少的 `todoRate` 與 `doingRate` 兩項 measures。
    - 原先在 BFF 層用 `Math.round()` 計算，違反 Rule 2 規格；改為 Cube 統一用 `floor()` 處理。

### ✅ 近期已解決 (2026-06-04 ETL 執行錯誤修復與 backfill_silver 重構)

- **varinst lookback 延長與空行防覆寫** (`d8ade48`):
    - `backfill_pivot.sql`：varinst 回溯範圍從 180 天延長至 365 天，覆蓋長流程任務（變數建立時間超過 180 天前的情形）。
    - 新增 `HAVING` 子句跳過全空資料列，防止空行以較新的 `_refresh_time` 覆蓋已正確的歷史資料。
    - `backfill_silver.sql`：將無法解析的維度（region/plant/factory/line）的 fallback 從 `'UNKNOWN'` 改為空字串。
- **ClickHouse 無效設定移除** (`d0753e3`):
    - `scripts/etl/execute_etl.py`：移除導致執行錯誤的 2 個無效 ClickHouse settings。
- **backfill_silver 共用 CTE 重構** (`ca465a7`):
    - 將 `backfill_silver.sql` 重構為共用 CTE 架構，減少重複邏輯（10 行新增、13 行刪除），同時保持 NULLIF region 修復。

### ✅ 近期已解決 (2026-06-03 V2/V1 四階維度 region 修復與全量回填)

**問題**: V2 任務選擇後無法帶出 Region/Plant，gold 層篩選 CNE/CNS 顯示空資料。

**根本原因（三層）**:
1. **ClickHouse LEFT JOIN 回傳 `''` 而非 NULL**：`COALESCE` 不跳過空字串，`mdm.region_code=''`（JOIN 失敗）被提早返回，備援邏輯從未執行。
2. **備援條件過嚴**：原邏輯只在 `lineName 為空` 時啟用 plant 備援，V1 有 lineName 但 MDM 查不到（如 NEP1）時備援也不啟動。
3. **Gold 層 ORDER BY 含 region**：`region=''` 和 `region='CNE'` 被視為不同 key，OPTIMIZE 無法去重，必須直接 DELETE。

**修復內容 (`sql/etl/dml/backfill_silver.sql`)**:
- 所有 `mdm.*` 欄位加上 `NULLIF(..., '')`，確保 JOIN 失敗的空字串被轉為 NULL
- 移除 region 備援的 `IF(lineName IS NULL)` 條件限制，改為只要精確 MDM 查不到就直接用 plant 備援
- 新增 `SETTINGS allow_experimental_analyzer = 0`（ClickHouse 25.8 analyzer bug workaround）

**回填範圍**: 2025-10 ～ 2026-05（8 個月），全部完成

**Gold 層清理** (`ALTER TABLE ... DELETE WHERE region = ''`):
- `rmv_l5_task_summary`: 3,028 筆刪除
- `rmv_l5_task_completion_phys`: 3,018 筆刪除
- `rmv_l5_milestone_phys`: 2,321 筆刪除
- `rmv_l5_acc_phys`: 3,963 筆刪除

**驗證結果 (2025-10 V2)**:
- Silver: CNE/WJ2=10,135 筆 ✅、CNS/DG3=6,342 筆 ✅、region='' 0 筆 ✅
- Gold: CNE/WJ2 有資料 ✅、CNS/DG3 有資料 ✅

**四階回推限制（設計邊界）**:
- `plant → factory` 是 1:N（DG3 有 7 個 factory），無法安全回推，V2 的 `factory` 維持 UNKNOWN
- `line_name` 在 MDM 中非唯一鍵（TZ-TEST 出現 29 個 plant），不可用 line 單鍵回推 plant

**暫存腳本（可清理）**: `scripts/check_gold_region.py`、`scripts/verify_silver_region.py`、`scripts/fix_gold_empty_region.py`、`scripts/verify_oct_v2.py`

### ⏩ 進行中 / 待處理
- **語義層對接**: 已建立 `L5TaskDetailsSuper` Cube，準備在前端報表啟用新欄位。
- **生產環境穩定運轉**: 持續觀察 ReplacingMergeTree 在高頻更新下的合併效能。
- **sync_unified_odbc.py 結構性風險（未修）**: `sync_full_table()` 採 TRUNCATE-before-INSERT 無回滾設計，任何 INSERT 失敗（非密碼問題）仍會留空表。建議改為先寫暫存表確認成功再替換，或至少 INSERT 失敗時嘗試回填。
- **未 commit 的修改**: 環境變數化的 5 個檔案（`export_silver_detail.py`、兩個 docker-compose、`init_pipeline.sh`、`claude.md`）以及 `sync_unified_odbc.py` fail-loud、`infra/monitoring/docker-compose.yml` 更新，目前僅在工作目錄，GitLab 未同步。
- **Grafana `main` 分支待清除**: GitHub 預設分支切到 `master` 後可刪除多餘的 `main`。

## 🎯 專案當前狀態
- **整體架構**: **V4.3 超級事實表 (Super Silver Architecture)**。
- **數據準確度**: 核心 KPI 與 UI 明細數據 100% 同步，且精確對齊業務目標。
- **資料夾狀態**: 已完成 ETL 資料夾清理，僅保留正式管線檔案。

## 待辦事項
- [x] 解決 W1 跨年數據對帳落差
- [x] 實作全新的 UI 明細寬表 V2
- [x] **將 UI 明細邏輯整合進核心 Fact Table (V4.3 升級)**
- [x] **實作 DML argMax 去重優化，解決資料重複問題**
- [x] **清理過時 ETL 程式碼與檔案**
- [x] **建立 `L5TaskDetailsSuper` 語義層模型**
- [x] 推送所有 V4.3 正式版邏輯至版本控制
- [x] **實作 7 日滾動積壓率分母優化 (2026-05-07)**
- [x] **更新 Cube.js 維度感知 Acc Rate 公式**
- [x] **完成全量 Gold 層數據回填**
- [x] **升級 Watermark 水位線表結構，新增資料最舊/最新時間欄位 (2026-05-27)**
- [x] **實作 ETL 智能自動接龍與防空窗 OOM 自我療癒機制 (2026-05-27)**
- [x] **擴充 --status 監控儀表板，整合展示真實資料時間跨度 (2026-05-27)**
- [x] 修復 V2/V1 四階維度 region 為空字串問題，完成 2025-10 至 2026-05 全量回填 (2026-06-03)
- [x] 修復 varinst lookback 365天、防空行覆寫 HAVING 子句 (2026-06-04)
- [x] 移除無效 ClickHouse settings 修復執行錯誤 (2026-06-04)
- [x] backfill_silver.sql 共用 CTE 重構 (2026-06-04)
- [x] 費率指標統一改為 floor() 整數百分比，符合 Rule 2 規格 (2026-06-05)
- [x] 新增 todoRate / doingRate 至 L5TaskPeriodic Cube (2026-06-05)
- [x] 建立 CH vs MSSQL 全線體對帳腳本 audit_all_lines.py，支援 period/vx-type 篩選與 dt 日期欄位 (2026-06-09)
- [x] 修正 MSSQL vx_type 查詢邏輯，對齊 Silver backfill_silver.sql MoNumber/NPE 覆蓋規則 (2026-06-09)
- [x] GitHub 機敏資訊清洗（密碼/IP/作者身份）+ ClickHouse 密碼旋轉 + CUBEJS_API_SECRET 更換 (2026-06-29)
- [x] sync_unified_odbc.py fail-loud sys.exit(1) patch (2026-06-29)
- [x] Grafana Bronze Sync Monitoring dashboard 建立（4 panels，正式環境 .76 datasource）(2026-06-30)
- [x] MSSQL_PASSWORD 環境變數補上，自動排程恢復正常，2026-07-02 首次成功驗證 (2026-07-02)
- [ ] 觀察 Super Silver 表在前端 Superset 的明細鑽取效能
- [ ] 清理暫存驗證腳本 check_gold_region.py, verify_silver_region.py, fix_gold_empty_region.py, verify_oct_v2.py
- [ ] sync_full_table() TRUNCATE 無回滾結構性風險修復（暫存表替換方案）
- [x] Grafana dashboard 雙線趨勢、精確 filter、GF_SERVER_ROOT_URL 完成調校（2026-07-03）
- [ ] 將工作目錄未 commit 修改推送至 GitLab（環境變數化 + fail-loud + monitoring docker-compose）
- [x] 315 工單規則決策：查證影響 69 萬筆任務，維持現狀不套用，.kiro spec 視為過時（2026-07-06）
- [x] 清洗 5 個含 IP/舊密碼的追蹤檔（memory-bank 三檔、grafana_dashboard_setup.md、monitoring compose→env 插值），commit `263dfa1`；並還原被誤刪的 `.gitignore`（2026-07-06）
- [ ] **GitHub 同步需走 cherry-pick**：本地 master 與 origin/master（filter-repo 清洗版）歷史完全分叉、本地歷史仍含舊機敏字串，**絕不可直接 force-push master**；需從 origin/master 建分支 cherry-pick 新 commits 後推送
- [ ] 監控主機部署注意：`infra/monitoring/docker-compose.yml` 改用必填變數，重啟前需在該主機建立 `infra/monitoring/.env`（MONITOR_HOST、GRAFANA_ADMIN_PASSWORD）
- [ ] commit 新建的 AI 知識庫（docs/08_ai_agent/、CLAUDE.md、sql/etl/dml/README.md 修正）與已刪除檔案的處置確認


