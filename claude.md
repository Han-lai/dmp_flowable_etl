# CLAUDE.md - DMP Flowable 快速上手指南 (Quick Start)

> [!IMPORTANT]
> **Git Push**: 接下來的任務都不要自動地幫我 push 到 GitHub 當中。 (No automatic pushing to GitHub.)

## 專案當前狀態 (2026-03-10 UPDATE)
本專案已完成 **L5 Insight API (FastAPI)** 之開發與部署，並實現了 **Split-Stack (服務拆分)** 架構。

### 最新完成 (2026-03-10)
- **L5 Insight API (FastAPI) 正式上線**:
  - 實作 `/api/l5/task-report` 終點，支援 GET/POST 複雜報表格式。
  - 整合 Pydantic 模型進行結構化驗證，提供月/週/日三位一體之數據產出。
- **服務架構分離 (Split-Stack)**:
  - 將 ClickHouse 與 API 拆分為獨立 Docker Compose 堆疊 (`docker-compose-api.yml`)。
  - 支援獨立管理與維護。
- **動態掛載部署 (Dynamic Runtime)**:
  - 採用 Volume-mount 模式掛載 `main.py` 與 `requirements.txt`。
  - 啟動時自動安裝依賴，支援透過 FileBrowser 即修即用。
- **全域文件去標籤化 (De-versioning)**:
  - 移除所有文檔與 API 終點中的 `v2` 標記，完成正式生產命名過度。

### 先前修復 (2026-02-26)
- **Vx 歸屬邏輯修復 (解決 V1 掛零異常)**:
  - **問題**: NPE 與 DG3 廠區的 V1 資料短少 (甚至為 0)，且全部湧入 V3 造成數量膨脹。
  - **根源**: Silver 層 `vx_type` 判斷序列將 `TASK_DEF_KEY_` 優先級置於頂層，導致本該由工單號 (MO) 強制轉為 V1 的特權工單被 `V3_` 開頭的自身屬性騎劫。
  - **解決**: 重新實作廠區限定之過濾白名單 (`Plant = DG3` 或 `Plant LIKE %NPE%`)。確保特定工單前綴 (196, 315 等) 優先轉換為 V1，並實機比對確認千筆以上的懸案任務已正確歸屬。
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
- **2026-03-10**: L5 Insight API (FastAPI) Deployment & Split-Stack Architecture.
- **2026-03-10**: Production Naming Transition (V2 Removal) Across Docs & Code.
- **2026-02-26**: Vx Attribution Logic Fix (DG3/NPE V1 vs V3 Correction).

### 其他待辦
- [ ] **VM 驗證**: 確認 API 在正式 VM 環境中的效能與 Portainer 通訊穩定度。
- [ ] **任務二**: 驗證 **L7 人員使用率 (User Utilization)** 指標 (目前仍暫緩)。
- [ ] 監控背景 REFRESH 任務的效能負擔。

