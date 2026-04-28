# CLAUDE.md - DMP Flowable 快速上手指南 (Quick Start)

> [!IMPORTANT]
> **Git Push**: 接下來的任務都不要自動地幫我 push 到 GitHub 當中。 (No automatic pushing to GitHub.)

## 專案當前狀態 (2026-04-19 UPDATE)
本專案目前已透過回復金層程式碼與 Cube.js 模型，完美重現並釐清了月/週報表數值相對 UI 放大的「重複累加現象」。目前處於業務定義決策階段。

### 最新完成 (2026-04-21)
- **技術設計規格書 (TDD v4.0) 完工**:
  - 完成正式化的 `DMP Flowable 數據分析平台技術設計規格書`。
  - **核心整併**: 納入 `ARRAY JOIN` 快照邏輯、EAV 透視、以及 ODBC 9萬筆/秒之壓測基準。
  - **聯動機制**: 建立了 `docs/` 下各專題深度文件之網狀連結（架構、指標、監控）。
  - **SOP 制定**: 完成「新增指標」的 6 步驟開發指南。
  - **清理**: 移除「影子比對」與硬體特定字眼，改用「數據審計」與「資源受限防禦」。

### 先前完成 (2026-04-19)
- **釐清 Cube.js 週/月放大現象**:
  - 將金層恢復使用 3 點事件的 `ARRAY JOIN`，並結合 Cube.js 的 `sum()`，成功重現了例如 V3/CNE 12月 Total 2864 筆 (UI僅2294筆) 的情形。
  - **證實**: 月/週指標因跨日軌跡而重複加總。已記錄至 Memory Bank 供後續分析。

### 先前完成 (2026-04-02)
- **Bronze 層優化完成**:
  - 完成 Bronze 資料庫重建，應用所有優化設定 (ORDER BY + Skip Index)
  - 清除 ops_metrics checkpoint，重新執行完整 ETL pipeline
  - 驗證優化後的 Bronze → Silver → Gold 資料轉換
- **ETL 效能比較分析**:
  - Silver 層改善: silver_facts +11.54%, silver_exclusion +18.94%
  - Gold 層效能下降: gold_milestone -153%, gold_acc -87%
  - 整體效能: -10.35% (29.63秒 → 32.70秒)
  - Silver 表資料量減少 61% (7.58M → 2.97M 筆)
- **專案清理與整理**:
  - 識別可刪除的測試/分析檔案: scripts/ 34個, 根目錄 21個
  - 確認 sql/etl/dml/ 所有檔案需保留 (正式使用中)
  - 所有 DML 檔案已正確使用 bronze.* 資料庫引用
- **資料庫狀態**:
  - bronze: 優化後的新資料庫 (52.88M 筆)
  - bronze_backup: 舊版資料庫備份 (60.63M 筆)

### 先前完成 (2026-03-16)
- **L5 效能與區域修復**:
  - 優化 `ARRAY JOIN` 邏輯，大幅降低查詢負載與 OOM 風險。
  - 實作多階層區域關聯，將全量報表中的 `UNKNOWN` 降至 0。
- **自動化刷新機制定時**:
  - Silver & Gold 層 MView 設定為每日凌晨 02:00 ~ 05:00 依序刷新。
- **Git 結構化 Commit**:
  - 將 Perf、Docs、Fix 拆分推行至 GitLab。

### 先前修復 (2026-02-26) [已簡化於 2026-04-15]
- **Vx 歸屬邏輯修復 (解決 V1 掛零異常)**:
  - **問題**: NPE 與 DG3 廠區的 V1 資料短少 (甚至為 0)，且全部湧入 V3 造成數量膨脹。
  - **根源**: Silver 層 `vx_type` 判斷序列將 `TASK_DEF_KEY_` 優先級置於頂層，導致本該由工單號 (MO) 強制轉為 V1 的特權工單被 `V3_` 開頭的自身屬性騎劫。
  - **解決**: 新增特定工單號規則，確保工單前綴 (196, 199, 200, 210, 212, 213) 優先轉換為 V1。
  - **2026-04-15 更新**: 簡化邏輯，移除冗餘的 DG3/NPE 廠區限制條件。
- **MDM 維度對應修復 (異廠同名線段)**: 
  - **問題**: Superset 上 DG3 廠區的 ST02 等線體在選擇 `Region: CNS` 時無資料。
  - **根源**: MDM 主檔中存在多條 `ST02`，分別隸屬 WJ5 (華東) 與 DG3 (華南)。Silver 視圖建構時僅依賴 `LineName` 去重，導致 DG3 誤判為 CNE。
  - **解決**: 於 Silver 層 (`03_silver`, `04_silver`) MDM 加入 `PlantCode` 進行雙重複合鍵 (`Line + Plant`) 交集比對與去重，徹底解決同名線段的歸屬錯亂，並完成 Data 重新載入。

### 最新完成 (2026-02-13)
- **Gold V2 Migration**: 修復 Gold View Detached 問題，遷移至 `gold.rmv_l5_task_completion_v2`。
- **Data Backfill**: 完成 `DG3/SMT/ST02` 資料回補。
- **L5 維度修復**: 解決 Gold 層五階維度 (Region/Plant/...) 為空的問題，確認為主從 MView 刷新延遲導致，已在重建腳本中加入 `sleep` 等待機制。
- **Cube 錯誤修正**: 修復 `cube_l5_task_periodic_v2_pivot.js` 因 `UNION` 欄位數量不一致導致的報錯。
- **ACC Rate 決策**: 確認 L5 累積完成率 (ACC Rate) 的「7天滾動分母」邏輯保留在 Cube 層，Gold SQL 層維持每日匯總。
- **L7 狀態**: L7 人員使用率 (`rmv_user_utilization`) 重建任務依據用戶要求暫緩 (Deferred)。

### 已完成 (2026-02-12)
- **MView 更新頻率調整**: 將 Silver/Gold 層的 Refreshable MView 更新頻率從 1 小時調整為 **48 小時**，以降低資源消耗。
- **安全重建腳本**: 建立 `scripts/etl/update_mviews_no_data_loss.py`，支援在不刪除 Bronze 層原始資料的情況下重建 MView。

### 已完成 (2026-02-10)
- **Cube Model 精簡**: 歸檔 5 個舊版模型，僅保留 2 個 V2 系列模型
  - 保留: `cube_l5_task_periodic_v2.js` (週期性報表)
  - 保留: `cube_l5_task_periodic_v2_pivot.js` (狀態比較報表)
  - 歸檔: 5 個舊版模型至 `cube/model/cubes/archive/`
- **維護效益**: 減少 71% 模型數量 (7→2)，統一使用 V2 進階邏輯
- **文件重構**: `PROJECT_AUDIT_REPORT.md` 完成三層架構對映修正，並暫時移除未啟用的 L7 指標。

### 核心功能 (2026-02-09)
- **累積比率 (Acc Rate) 修正**: 實作「7 天滾動總量」分母邏輯，解決週末數據波動問題，達成 12/28 基準值 (7%) 對齊。
- **時光機優化 (V2 Final)**: 成功實作 **Triple-OR 篩選邏輯**，全面支持 Superset Dashboard 與 Chart 不同時間格式（含微秒），徹底解決類型轉換報錯。
- **維度標準化**: 完成「五階維度」與「組織名稱（廠區）」的最終對齊與繁體化。
- **數據準確**: 完成 12/25 WJ2/E5 數據完全對齊 (ACC=40)，並驗證 CNS DG3 廠區數據路徑。


---

## 開發常用指令

### 1. 數據同步 (Bronze)
```powershell
# 同步大表與維度表
python scripts/etl/sync_batches_consolidated.py
```

### 2. 重建管線 (Silver / Gold)
```bash
# 完整重建 Bronze → Silver → Gold
python scripts/etl/execute_etl.py

# 不中斷更新 MView
python scripts/etl/update_mviews_no_data_loss.py
```

### 3. API 服務部署 (FastAPI)
```bash
# 啟動 API 堆疊 (埠位 7088)
docker-compose -f infra/docker-compose-api.yml up -d

# 重啟 API 以加載新代碼
docker restart flowable_pipeline_api
```

### 3. 驗證 (scripts/validation/ 下各子目錄)
```powershell
# 快速統計
python scripts/validation/data_explore/quick_stats.py
```

---

## 核心目錄結構
- `sql/etl/`: Bronze → Silver → Gold 完整管線 SQL。
- `docs/`: 📂 系統化技術文件 (分 Architecture, Deployment, Metrics, API, Monitoring, Reports)。
- `scripts/`:
  - `etl/`: 生產同步與重建腳本 (7 個)。
  - `setup/`: 一稱性設定腳本。
  - `validation/`: 驗證腳本 (與其子類及 debug 目錄)。
- `infra/`: ClickHouse + JDBC Bridge + API + Monitoring 部署設定。
- `cube/`: Cube.js 語意層模型。
- `api/`: FastAPI 原始碼。

---

## 待辦事項 (Backlog)

### 已完成修正
- **2026-04-02**: Bronze 層優化完成與 ETL 效能驗證
- **2026-04-02**: 識別可清理的測試/分析檔案
- **2026-03-10**: L5 Insight API (FastAPI) Deployment & Split-Stack Architecture.
- **2026-03-10**: Production Naming Transition (V2 Removal) Across Docs & Code.
- **2026-02-26**: Vx Attribution Logic Fix (DG3/NPE V1 vs V3 Correction).

### 其他待辦
- [ ] **Gold 層效能調查**: 調查 Gold 層效能下降原因 (資料量減少但查詢變慢)
- [ ] **專案清理**: 清理測試/分析檔案 (scripts/ 34個, 根目錄 21個)
- [ ] **VM 驗證**: 確認 API 在正式 VM 環境中的效能與 Portainer 通訊穩定度。
- [ ] **任務二**: 驗證 **L7 人員使用率 (User Utilization)** 指標 (目前仍暫緩)。
- [ ] 監控背景 REFRESH 任務的效能負擔。
