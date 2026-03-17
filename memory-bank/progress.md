# 專案進度 - DMP Flowable

## 已完成里程碑

### 2026-03-16 (今日進度 - SQL 邏輯優化與自動刷新機制完善)
- ✅ **L5 指標運算效能優化 (ARRAY JOIN)**:
    - **改動**: 將 `06_gold_kpi_task_completion.sql` 原本負荷重擔的 `CROSS JOIN` 改寫為 `ARRAY JOIN`。
    - **成效**: 運算中間層數據從 7.5 億筆降至 1000 萬筆級別，效能提升 98%，徹底根除 OOM (記憶體溢出) 風險。
- ✅ **全量區域修復 (Multi-Level Region Mapping)**:
    - **邏輯**: 於 `04_silver_fact_tasks.sql` 實作多接層關聯，若線別缺失則自動降級透過「廠區」映射 Region。
    - **結果**: 成功將 Silver 與 Gold 層原本 147 萬筆的 `UNKNOWN` 區域數據清零。
- ✅ **階層式錯開刷新排程 (Staggered Refreshes)**:
    - **配置**: 設定每日凌晨 02:00 ~ 05:00 依序啟動 Silver 與 Gold 各層刷新。
    - **目的**: 確保資料處理流程 (Bronze -> Silver -> Gold) 具配順序性，並避開系統負擔高峰。
- ✅ **人員資料版本一致性**:
    - **變更**: 確認所有人員關聯 Table (如 `common_mdm_employee_master`) 已全數改用 `0202` 快照版本，避免數據遺漏。
- ✅ **Git 提交結構整理**:
    - **操作**: 將優化 (Perf)、文件 (Docs)、修正 (Fix) 拆分為三個清晰的 Commit 並完成 GitLab 推送。

### 2026-03-10 (今日進度 - L5 Insight API 正式上線與架構分離)
 - ✅ **L5 Insight API (FastAPI) 正式版**:
    - **終點**: 實作 `/api/l5/task-report`，同時支援 `GET` 與 `POST` (JSON Body)。
    - **功能**: 提供複雜的月、週 (ISO)、日報表格式，自動計算各狀態之 Qty 與 Percentage，並支援多維度過濾。
    - **規範**: 移除所有 `v2` 標記，完成生產環境命名過渡。
- ✅ **服務架構分離 (Split-Stack)**:
    - **配置**: 將 ClickHouse 與 API 拆分為獨立的 Docker Compose 堆疊 (`docker-compose-api.yml`)，實現解耦管理。
    - **連線**: 透過 VM 正式 IP (`REDACTED_IP`) 進行容器間通訊，並更新 `.env` 配置。
- ✅ **動態掛載部署模式 (Dynamic Runtime)**:
    - **實作**: 採用 `python:3.10-slim` 基礎映像檔，透過 Volume 掛載 `main.py` 與 `requirements.txt`。
    - **自動化**: 容器啟動時自動執行 `pip install`，支援透過 FileBrowser 即時更新程式碼而無需重新 Build Image。
- ✅ **部署手冊與 Walkthrough**: 產出 `DEPLOYMENT_GUIDE.md` 與 `walkthrough.md`，詳述 Port 7088 之存取與維護 SOP。

### 2026-03-09 (先前進度 - Cube Pivot 與 Enhanced L5 API 實作)
- ✅ **Cube.js V3 Pivot 模型升級**:
    - **問題**: 在 Superset 的 Pivot 報表中，若 User 不點選特定的 `factory` 或是 `line`，Cube.js 預設無法將全部的資料向上加總（會因為依賴而報錯，或是造成百分比採取「平均的平均」算錯）。
    - **解決方案**: 捨棄在容器內直接修改唯讀檔案，新建 `cube_l5_task_periodic_v3_pivot.js`。利用 `FILTER_PARAMS.isSet()` 的特性，當未捕捉到前端過濾器時，強迫賦值字串 `'ALL'`；同時把百分比 (`task_pct`) 計算從 SQL 中拔除，改在 Measure 階段進行真正的 `sum() / sum()` 運算。
    - **成果**: 完美達成報表未過濾狀態下的全盤加總檢視。
- ✅ **Enhanced L5 Task Completion API (FastAPI)**:
    - **需求**: 使用者需要一個能同時呈現「月、週、日」數據，並包含多種狀態百分比（Doing+Done, Acc）的複雜報表結構。
    - **實作**: 於 `api/main.py` 新增 `/api/l5/task-report` 終點。支援動態計算月份結尾、ISO 週次與最後 7 天的數據，並自動計算各狀態之 Qty 與 Percentage。
    - **數據驗證**: 成功驗證 CNE WJ2 於 12/25~12/31 的數據與使用者提供之基準完全一致。
    - **部署模式**: 完成 Docker 化部署配置，包含 `Dockerfile`, `requirements.txt` 及 `docker-compose.yml` 服務掛載。支援透過 `.env` 變數 `VOLUMES_ROOT` 指定統一存儲路徑（如 `/home/docker-data/flowable_pipeline_api`）。
    - **指南**: 產出 `docs/DEPLOYMENT_GUIDE.md` 提供完整 VM 部署 SOP。
- ✅ **產出 L5 任務完成率報告**:
    - **背景**: 為了向管理層說明 ClickHouse V3 (排除 `Recycle Plan` 等特殊任務) 與舊有 Baseline 之間的數字鴻溝。
    - **產出**: 針對 `CNE WJ2` 與 `CNS DG3` 分別產出了純淨的數據比較矩陣報告。
    - **歸檔**: 正式將整合後的報表歸檔於 `docs/reports/L5_Data_Discrepancy_Report_202612.md` 中留存。

### 2026-03-06 (先前進度 - L5 雙產線效能基準驗證與進階監控)
- ✅ **雙產線高併發壓測完成 (DG3/SMT/ST02 & WJ2/NBU/E5)**:
    - **測試配置**: 模擬 10 人併發 × 100 次隨機日期查詢。
    - **效能指標**: Pivot SQL (報表複雜結構) QPS 保底 10.5 筆/秒，P50 延遲 < 0.9s；Standard SQL (純聚合) QPS 破 50 筆/秒，P50 延遲 < 0.2s。
    - **資源證明**: 記憶體峰值 < 405 MiB (遠低於 1 GiB 上限)，資料壓縮比達 6.6 倍。
    - **瓶頸定位**: 確認約 80% 延遲來自 Cube.js 產生的 Pivot (6段 UNION ALL) 重複掃描結構，ClickHouse 引擎本身運算能力過剩。
- ✅ **五大交付文件產出與歸檔**:
    - `benchmark_result.md`: 原始測試輸出數據記錄
    - `monitoring_architecture_and_status.md`: 完整架構與正式效能驗收報告 (PASS)
    - `benchmark_briefing.md`: 主管會報專用摘要 (白話重點版)
    - `benchmark_runbook.md`: 壓測重現標準作業程序 (SOP)
    - `dashboard_usage_guide.md`: 給管理層的 Dashboard 判讀與情境指南
- ✅ **Grafana 儀表板補建 (Benchmark-Driven Panels)**:
    - 新增 **Query Latency Distribution** (分色點狀圖 + 1000ms 閾值線)。
    - 新增 **Real-time QPS** (每分鐘吞吐量柱狀圖 + 10 QPS 安全線)。
    - 新增 **Per-Query CPU vs Duration** (CPU/時間/I/O Wait 分解散點圖)。
    - 新增 **Table Storage Overview** (精準追蹤核心表格的空間與壓縮比)。
    - 修復並優化了 `node_exporter` CPU stale series 問題，實作 ClickHouse vs Others vs Host 的面積堆疊圖 (Stacked Area)。

### 2026-03-05 (今日進度 - L5 ClickHouse 三回合壓力測試完成)
- ✅ **三回合遞進式壓測 (clickhouse-benchmark)**:
    - **Round 1 (基線)**: 簡化 GROUP BY SQL → QPS 411.8, P95 14ms
    - **Round 2 (真實 Superset)**: 完整 Cube.js CTE+UNION ALL+Window Function SQL → QPS 87.4, P95 173ms
    - **Round 3 (全域掃描)**: 拔除所有廠區過濾條件 → QPS 70.0, P95 177ms
    - **結論**: 三回合全數通過效能目標 (QPS > 50, P95 < 1s)，ClickHouse 效能「能力過剩」。
- ✅ **壓測腳本建立**:
    - `stress_test_l5_benchmark.py`: 產生真實 Cube.js SQL (單廠區過濾)
    - `stress_test_l5_global.py`: 產生全域掃描無過濾 SQL
- ✅ **文件更新**: 將三回合對比數據寫入 `docs/monitoring/monitoring_architecture_and_status.md`
- ✅ **cAdvisor Port 修正**: `docker-compose.monitor.yml` 中 cAdvisor 映射改為 8085:8080

### 2026-03-05 (早期進度 - L5 效能監控儀表板升級)
- ✅ **Grafana 儀表板 Storytelling 佈局重構**:
    - **設計**: 將 8 個面板劃分為 Macro Health (系統大盤)、L5 Query Impact (效能核心)、Deep Dive (深度剖析) 三層次的 12 欄網格佈局。
    - **優化**: 將資源消耗與 L5 Annotation 精確對接，並移除動態 instance 標籤的干擾，統一採用 `docker-host` 以提高穩定性。
- ✅ **高保真 (High Fidelity) 記憶體尖峰捕捉**:
    - **問題**: 發現 Prometheus 的 15 秒採樣頻率會漏掉 L5 亞秒級查詢的瞬時記憶體高峰 (約 300MB+)。
    - **解決**: 於 Deep Dive 區塊新增直讀 `system.query_log` 的 SQL Panel，確保每一次 0.x 秒的查詢波動皆能被精確點狀呈現。
- ✅ **查詢來源追蹤 (Query Source Tracking)**:
    - **實作**: 透過解析 `http_user_agent` 與 `client_name`，於 Expensive Queries 表格中新增 `source` 欄位。
    - **效益**: 現已能精確區別系統中哪些資源消耗來自 Cube.js (Superset)、DBeaver 手動操作或 Python 測試腳本。
- ✅ **併發壓力測試腳本開發**:
    - **產出**: 建立 `scripts/validation/stress_test_l5.py`，模擬 10 人併發隨機維度組合的 L5 查詢，為基準測試做好準備。


### 2026-02-26 (今日進度 - 四條件 DONE 驗證完成)

- ✅ **四條件 QAS vs CH Done 數量驗證**:
    - **驗證範圍**: 四個核心業務條件，2025-12-25 至 12-31 每日數據
        - V1 / CNS / DG3 / SMT / ST02
        - V3 / CNS / DG3 / SMT / ST02
        - V3 / CNE / WJ2 / NBU / E5
        - V1 / CNE / WJ2 / NPE / NPE3
    - **工具**: `scripts/validation/l5_l7/verify_4_done.py`
    - **結果**: 全部 **OK**，QAS 與 ClickHouse Gold 層 (`rmv_l5_task_completion_v2`) Done 數量差異均為 0。
    - **結論**: 先前修復的兩個 bug（Vx 歸屬順序錯誤、異廠同名線段誤判）已完全生效，Silver / Gold 資料與 QAS 源頭完全同步。

### 2026-02-26 (Silver 層業務邏輯與維度修復)
- ✅ **Vx 歸屬邏輯修復 (特權工單誤判 V3 問題)**:
    - **問題**: 發現 `V1 / CNE / WJ2 / NPE / NPE3` 與 `V1 / CNS / DG3 / SMT / ST02` 的 V1 任務數量在 金層 (Gold) 完全掛零，且 V3 數據異常膨脹。
    - **根源調查**: `04_silver_fact_tasks.sql` 在給工單貼 `vx_type` 標籤時，把 `TASK_DEF_KEY_ LIKE 'V3%'` 放在了判斷的最前面。導致原本依據業務規則應該被強制判定為 V1 的特權工單 (如 196, 315 開頭的工單)，因為流程圖自帶 V3 屬性而被誤殺。
    - **解決方案**: 重構 Silver 層邏輯，實作「廠區與工單號聯合判斷」。為 `DG3` 廠區與包含 `NPE` 的廠區建立白名單，讓符合前綴的工單優先轉換為 V1，其餘量產線體 (如 WJ2/E5) 則繼續回歸流程圖預設標籤。
    - **結果**: 執行 `verify_final_post_fix.py` 嚴謹比對 ClickHouse 與 SQL Server (QAS) 雙軌資料，確認千筆以上的迷路數據已完美回歸 V1，解決掛零與爆增的雙向異常。

- ✅ **異廠同名線段 (Duplicate Lines in MDM) 歸屬修復**:
    - **問題**: 發現 DG3 廠區的 `ST01~ST05` 在 Cube.js 查詢時，若選擇 `Region: CNS` 會發生查無資料 (Data Missing) 的異常。
    - **根源調查**: 追溯發現 MDM 底層主檔 (`bronze.common_mdm_line_desc_master`) 中，`ST02` 這個線名分別存在於兩處：WJ5(CNE) 與 DG3(CNS)。原先 `silver.mv_dim_mfg_five_level` 五階視圖建立時僅以 `LineName` 做 `ORDER BY` 去重，導致 DG3 的單子被錯誤套用成 CNE 的維度。
    - **解決方案**: 於 `03_silver_pivot_and_hierarchy.sql` 中讓五階視圖保留 `(plant_code, line_name)` 雙主鍵去重。並於 `04_silver_fact_tasks.sql` 的 LEFT JOIN 條件中加入 `mdm.plant_code = varinst_plant` 的雙重驗證。
    - **結果**: 重建 Silver 與 Gold 層後，DG3/SMT/ST02 等同名線體資料成功回歸 CNS 轄區，Superset 報表呈現正常 (ST02 = 56,640筆)。

### 2026-02-13 (今日進度 - Gold 修復)
- ✅ **Gold 層視圖修復 (V2 Migration)**:
    - **問題**: 原本的 `gold.rmv_l5_task_completion` 視圖因 Metadata 錯亂導致 detached 且無法恢復 (需 Experimental Feature)。
    - **解決**: 建立新視圖 `gold.rmv_l5_task_completion_v2`，並成功遷移。
    - **回補**: 針對 `DG3/SMT/ST02` 執行手動回補 (Backfill)，寫入 176 筆聚合資料，解決報表空值問題。
- ✅ **Cube.js 模型同步更新**:
    - **修正**: 將 `cube_l5_task_periodic_v2.js` 與 `cube_l5_task_periodic_v2_pivot.js` 資料來源指向 V2 視圖。
    - **文檔**: 更新 `README_L5_DASHBOARD_CUBE.md` 反映 V2 架構。

### 2026-02-10 (此前進度)
- ⚠️ **發現 V2 Pivot 模型 ACC Rate 計算錯誤**:
    - **問題**: `cube_l5_task_periodic_v2_pivot.js` 在 Pivot 轉換時遺漏了 `acc_total_qty` 欄位
    - **影響**: ACC Rate 使用錯誤的分母 (`total_qty` 而非 7天滾動總量),導致 2025-12-28 等日期出現異常大的比率
    - **根源**: 第 161 行使用 `total_qty` 作為分母,應使用 `acc_total_qty`
    - **狀態**: 已建立修正計劃 (`implementation_plan.md`),待明日實作

### 2026-02-10 (今日進度 - 早期)
- ✅ **Cube Model 架構優化與歸檔**:
    - **模型精簡**: 將 7 個 Cube 模型精簡至 2 個 (減少 71% 維護負擔)
    - **歸檔清單**: 移動 5 個舊版模型至 `cube/model/cubes/archive/`:
        - `cube_gold_l5_task_completion.js` (舊版 Gold 層模型)
        - `cube_l5_dashboard_summary.js` (舊版 Dashboard 模型)
        - `cube_l5_task_completion.js` (舊版 Pivot 模型)
        - `cube_l5_task_periodic.js` (V1 週期性報表)
        - `cube_user_utilization.js` (用戶利用率模型)
    - **保留模型**: 僅保留 V2 系列
        - `cube_l5_task_periodic_v2.js` (週期性報表，支援 7 天滾動分母)
        - `cube_l5_task_periodic_v2_pivot.js` (狀態比較報表，支援歷史查詢)
    - **文件更新**: 更新 `README_L5_DASHBOARD_CUBE.md` 說明當前架構
    - **效益**: 統一使用 V2 進階邏輯，簡化維護流程

## 進行中的工作

### 2026-02-11
- ✅ **V2 Pivot ACC Rate 計算修復**:
    - **修正**: 在 `cube_l5_task_periodic_v2_pivot.js` 中補回 Month/Week 的 `acc_total_qty` 欄位
    - **驗證**: 確保 Day 粒度使用 7天滾動總量，Month/Week 使用週期總量作為分母
    - **交付**: 提供 Python 驗證腳本 `scripts/validation/verify_gold_acc.py` 供用戶自行核對 Gold 層數據

- ✅ **2026-02-11**:
    - **Documentation**: Overhauled `PROJECT_AUDIT_REPORT.md`, clarified ACC logic, removing L7.
    - **QAS Verification**:
        - Confirmed **Zero** V1 tasks in `WJ2/NBU` scope (QAS Env).
        - Confirmed V1 tasks in `DG3` belong to `NPE`, not `SMT`.
        - Verified standard SQL for `WJ2/NBU/E5` (Count: 184) and `DG3/SMT/ST02` (Count: 3636).
    - **Spec Compliance**:
        - Updated Vx Attribution Priority in Spec to match Code (`Key > Mo`).
        - Added warning about missing variables (Region/Line) in QAS data.
    - **Feature**: Removed L7 User Utilization from active scope.
    - **架構校正**: 重寫 `PROJECT_AUDIT_REPORT.md` 的 End-to-End Table Mapping，補齊 Bronze/Silver/Gold 完整流向。
    - **邏輯釐清**: 明確定義 ACC Rate 在 Daily (Rolling) 與 Week/Month (Fixed Period) 的計算差異。
    - **術語優化**: 將「期末快照」與「轉結水位」白話化為「期末狀態」與「未完成積壓」。
    - **L7 移除**: 應要求暫時移除 L7 人員使用率相關內容，聚焦於 L5 指標。
    - **模型簡化**: 明確標記舊版 Pivot 模型為 Deprecated，僅保留 V2 Standard 與 V2 Pivot。

### 2026-02-10 (昨日進度)
- ✅ **L5 Acc Rate 指標邏輯修正**:
    - **核心問題**: 解決週末/連假期間因當日活動量 (`total_task`) 驟減導致 Acc Rate 暴飆 (如 12/28 達 418%) 的問題。
    - **解決方案**: 
        - **日報表**: 引入「7天滾動總量」作為分母，平滑波動，確保 12/28 數據準核對齊為 7%。
        - **週/月報表**: 自動採用週期內的總量作為分母。
- ✅ **L5 週期報表模型 (V2) 最終穩定化**:
    - **技術突破**: 解決 Superset Chart 傳送帶有微秒的 Timestamp (`.000000`) 導致的「Cannot convert string to Date」轉換錯誤。
    - **魯棒性優化**: 實作 `params` CTE 的 **Triple-OR 篩選邏輯**。透過「字串對字串」比對技術，全方位支持 Dashboard 與 Chart 的不同時間篩選格式。
    - **UI 優化**: 修正五階維度名稱 (如「廠區」字樣) 與排序邏輯。
- ✅ **CNS DG3 資料核帳**: 協助用戶確認 CNS DG3 廠區的線體對應關係（S06 對應 ST06），並驗證 12/31 數據準確性。

### 2026-02-06
- ✅ **L5 週期報表架構優化 (Refactoring)**:
    - **Phase 1 (SQL Standard)**: 建立 `sql/etl/dynamic_periodic_report.sql`，採用「參數推論 (Inference)」邏輯，自動依據日期範圍判斷當月/歷史模式，解除對 Superset Jinja 的依賴。
    - **Phase 2 (Cube V2)**: 實作新模型 `cube_l5_task_periodic_v2.js`，將所有運算邏輯下沉至 SQL CTE，Cube 僅負責 Schema Mapping，大幅減輕維護負擔。
- ✅ **L5 週期報表架構優化 (Refactoring)**:
    - **Phase 1 (SQL Standard)**: 完成 `sql/etl/dynamic_periodic_report.sql` 標準化，改採參數推論邏輯 (Inference Logic)。
    - **Phase 2 (Cube V2)**: 成功部署 `cube_l5_task_periodic_v2.js`，實現 Logic Push-down 架構。
    - **關鍵技術突破**: 解決 View Predicate Pushdown 失效問題，改用 Cube SQL Injection + Filter Separation 技術，實現「時光機 (Time Machine)」任意日期回溯與「8天滑動視窗」顯示。
- ✅ **L5 週期報表架構優化 (Refactoring - V2 Final)**:
    - **Phase 1 (SQL Standard)**: 邏輯 100% 下沉至 Clickhouse，解除對 BI 工具特定語法的依賴。
    - **Phase 2 (Cube V2)**: 實現「時光機 (Time Machine)」架喚，透過 Filter-Display 分離技術突破日期篩選限制。
    - **Phase 3 (Superset Integration)**: 解決 Dashboard 帶入 ISO Timestamp 的類型轉換錯誤，達成「選一天看全週」的穩定功能。
- ✅ **L5 週期性報表完成 (Stable Dual-Axis)**:
    - 成功實作 Superset 混合圖表 (Mixed Chart) 的自定義排序 (`periodSortOrder`) 與雙軸顯示 (Quantity + Rate)。
    - 完成 `cube_l5_task_periodic.js` 的穩定版開發 (Month/Week/Day 混合顯示)，確保 ClickHouse 函數相容性。
    - 建立 `docs/L5_Completion_Superset_Guide.md` 作為交付文件，記載設定參數與專案完成度。
- ✅ **L5 任務週期報表優化 (Mixed Chart Sorting)**:

### 2026-02-05
- ✅ **Gold 層架構修復 (Background Refresh Logic)**:
    - 解決 `gold.rmv_l5_task_completion` 定時刷新失敗問題 (修正 JOIN 語法為 CROSS JOIN)。
    - 資料恢復完成並與基準值對應 (Done=192, ACC=41 for 12/25)。
- ✅ **12/25 數據基準再確認**:
    - 每日任務數 (Daily Task Count) 確立為 192 筆。
    - 累積在途量 (ACC) 確立目標值為 40 筆 (目前 41 筆，1 筆差異調查中)。
- ✅ **Cube.js 模型架構分拆 (Dual-File Architecture)**:
    - `cube_l5_task_completion.js`: 保持「轉置版 (Pivoted)」，穩定支援 Superset 樞紐分析表。
    - `cube_l5_task_chart.js` [NEW]: 「寬表版 (Wide)」，專用於 Superset 混合圖表 (Mixed Chart) 與 Tooltip 百分比顯示。

### 2026-02-04
- ✅ **L5 指標業務邏輯修正與對齊**:
  - **Vx 歸屬修正**: 修正歸類權重 (TaskDefKey > moNumber)，解決跨流程 (V1 call V3) 的歸屬偏差問題。
  - **時點快照修正**: 捨棄「目前狀態」改採「歷史快照時點」判定，解決歷史報表隨時間變動的問題。
  - **累計在途量 (Acc) 修正**: 實作「7 天滑動活動視窗」邏輯，達成 12/25 數據 (40 筆) 完全對齊。
- ✅ **指標定義文件更新**: 於 `docs/03_1_columns_defin.md` 同步更新業務邏輯與修正歷程。
- ✅ **L5 週期性指標報告**: 生成 `docs/reports/L5_Periodic_Metrics_Report_20260204.md` (涵蓋 W51, W52, W01, Dec)。
- ✅ **差異調查與記錄**: 深入分析 DONE 數量差異 (WJ2/E5 12/30, 12/31)，確認源於 Recycle Plan 任務，已記錄為已知差異並應戶要求保留。

### 2026-02-03
- ✅ **L5 指標建立與三方驗證完成**: 達成 100% 數據對稱 (MSSQL Raw vs 0202 Benchmark vs CH Gold: 192 筆)
- ✅ **架構結構性修復 (Refreshable Pivot)**: 將 `silver.mv_varinst_pivoted` 改為 `REFRESHABLE MATERIALIZED VIEW`
- ✅ **技術文件全面現代化 (v2.1)**: 完成 6 份核心手冊的編撰，並保留了詳細的 `PROJECT_STRUCTURE.md` 目錄樹
- ✅ **環境大掃除**: 整合歸檔 12 份冗餘文件，移除 `scripts/` 下約 100 份一次性腳本，**並清理根目錄僅餘 5 個核心檔案**
- ✅ **五階維度修復**: 修正 `mv_dim_mfg_five_level`，Plant 完整度提升至 90%



- ✅ 確認 VxType 歸屬邏輯已在 Silver 層實作
- ✅ 確認 Region 維度已透過 MDM 補齊
- ✅ 發現數據差異 (198 vs 180)，初步分析為時間篩選邏輯差異
- ✅ 建立 memory-bank 目錄結構
- ✅ **技術文件更新 (Rebuild 版)**
  - `ARCHITECTURE_OVERVIEW.md` - 新建架構總覽
  - `silver_mviews_architecture.md` - 更新為 3 張 MVIEW
  - `data_pipeline_diagram.md` - 更新為單路徑 + Refreshable MView

### 2026-02-03 (Early)
- ✅ 恢復 `VARINST` 資料同步 (17.3M 筆, finish at 2026-01-08)
- ✅ 恢復 `TASKINST` 資料同步 (1.48M 筆, finish at 2026-01-08)
- ✅ 驗證 `Silver Layer (mv_fact_task_vx)` 資料正確注入 (1.49M 筆)
- ✅ 清理 4 個過期衝突的 Silver MViews (`mv_fact_task_vx_attribution_*`)，修復 `UNKNOWN_IDENTIFIER` 錯誤
- ✅ `PROCINST` 資料同步 (完成, Snapshot 0108)
- ✅ 修復 `silver.mv_fact_task_vx` MVIEW 定義 (移除 Alias 避免解析錯誤)
- ✅ 實作 Sync Script (`sync_batches_consolidated.py`) 的自動重試與批次縮小機制 (4小時)

### 2026-01-29
- ✅ 完成資料同步驗證
- ✅ Data Pipeline 架構重建 (sql/etl)

### 2026-01-15 (之前)
- ✅ Bronze 層 18 張表同步完成
- ✅ Silver 層 4 張 RMV 建立完成
- ✅ Gold 層 2 張 RMV 建立完成
- ✅ Cube.js 語意層 API 完成
- ✅ 11 個指標與 Benchmark 邏輯等價驗證

## 暫緩項目
- ⏸️ 逾期在途業務事件數 (缺 HealthSettings 表)
- ⏸️ 自動化排程 (目前手動執行)

- [x] 驗證 L7 人員使用率 (User Utilization) 指標 (因 User 要求暫緩修復)
    - [x] 針對 11、12 月份數據進行「五個條件」驗證 (嚴格 V3 邏輯)
    - [x] 核對 PowerUser 與 None Group 的排除邏輯
    - [x] 確認分母 (Config Users) 與分子 (Active Users) 定義是否符合預期
- [x] **修復**: L5 Gold MView 維度缺失問題
    - 解決方案: 於重建腳本中加入 `sleep(2)` 等待 Silver MView 刷新
    - 狀態: `gold.rmv_l5_task_completion` 已包含完整 Region/Plant/Factory/Line 資料
- [x] **決策**: ACC Rate 427% 異常修正
    - 用戶決定保留 Cube.js V2 模型中的 Rolling 7 Days 邏輯
    - Gold SQL (`rmv_l5_task_completion`) 維持每日匯總邏輯 (Status Quo)
- [x] 執行 MView 重建腳本 `scripts/etl/update_mviews_no_data_loss.py` 完成 (48hr 更新生效)


