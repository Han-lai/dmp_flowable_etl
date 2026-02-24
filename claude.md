# CLAUDE.md - DMP Flowable 快速上手指南 (Quick Start)

## 🎯 專案當前狀態 (2026-02-10 UPDATE)
本專案已完成 **Cube Model 架構優化** 與 **L5 週期報表 V2 全面校正**。

### 最新完成 (2026-02-13)
- **Gold V2 Migration**: 修復 Gold View Detached 問題，遷移至 `gold.rmv_l5_task_completion_v2`。
- **Data Backfill**: 完成 `DG3/SMT/ST02` 資料回補。
- **L5 維度修復**: 解決 Gold 層五階維度 (Region/Plant/...) 為空的問題，確認為主從 MView 刷新延遲導致，已在重建腳本中加入 `sleep` 等待機制。
- **Cube 錯誤修正**: 修復 `cube_l5_task_periodic_v2_pivot.js` 因 `UNION` 欄位數量不一致導致的報錯。
- **ACC Rate 決策**: 確認 L5 累積完成率 (ACC Rate) 的「7天滾動分母」邏輯保留在 Cube 層，Gold SQL 層維持每日匯總。
- **L7 狀態**: L7 人員使用率 (`rmv_user_utilization`) 重建任務依據用戶要求暫緩 (Deferred)。

### 已完成 (2026-02-12)
- **MView 更新頻率調整**: 將 Silver/Gold 層的 Refreshable MView 更新頻率從 1 小時調整為 **48 小時**，以降低資源消耗。
- **安全重建腳本**: 建立 `scripts/rebuild/update_mviews_no_data_loss.py`，支援在不刪除 Bronze 層原始資料的情況下重建 MView。

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

## 🛠️ 開發常用指令

### 1. 數據同步 (Bronze)
```powershell
# 同步大表與維度表
python scripts/rebuild/sync_batches_consolidated.py
```

### 2. 重建管線 (Silver / Gold)
```powershell
# 完整重建 Bronze → Silver → Gold
python scripts/rebuild/execute_rebuild.py

# 不中斷更新 MView
python scripts/rebuild/update_mviews_no_data_loss.py
```

### 3. 驗證 (scripts/validation/ 下各子目錄)
```powershell
# 快速統計
python scripts/validation/data_explore/quick_stats.py
```

---

## 📂 核心目錄結構
- `sql/rebuild/`: Bronze → Silver → Gold 完整管線 SQL。
- `docs/`: 核心技術手冊 (01~06 序號排列)。
- `scripts/`:
  - `rebuild/`: 生產同步與重建腳本 (7 個)。
  - `setup/`: 一次性設定腳本。
  - `validation/`: 驗證腳本 (分 7 個子類：date_audit, infra_check, data_explore, logic_verify, gold_layer, l5_l7, debug)。
- `docker/`: ClickHouse + JDBC Bridge 部署設定。
- `cube/`: Cube.js 語意層模型。

---

## 📝 待辦事項 (Backlog)

### 已完成修正
- **2026-02-11**: QAS Verification (WJ2/DG3 V1 checking) & Spec Compliance (Vx Priority).
- **2026-02-11**: Documentation Overhaul (Audit Report) & L7 Removal.

### 其他待辦
- [ ] **1 筆差異排除**: 將 12/25 的 ACC 數據從 41 修正為 40 (篩選器細調)。
- [ ] **任務二**: 驗證 **L7 人員使用率 (User Utilization)** 指標 (目前暫緩，已從文件移除)。
- [ ] 監控背景 REFRESH 任務的效能負擔。

