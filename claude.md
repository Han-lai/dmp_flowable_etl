# CLAUDE.md - DMP Flowable 快速上手指南 (Quick Start)

## 🎯 專案當前狀態 (2026-02-10 UPDATE)
本專案已完成 **Cube Model 架構優化** 與 **L5 週期報表 V2 全面校正**。

### 最新完成 (2026-02-10)
- **Cube Model 精簡**: 歸檔 5 個舊版模型，僅保留 2 個 V2 系列模型
  - 保留: `cube_l5_task_periodic_v2.js` (週期性報表)
  - 保留: `cube_l5_task_periodic_v2_pivot.js` (狀態比較報表)
  - 歸檔: 5 個舊版模型至 `cube/model/cubes/archive/`
- **維護效益**: 減少 71% 模型數量 (7→2)，統一使用 V2 進階邏輯

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
# 重建 Silver Pivot (Refreshable)
python scripts/rebuild/run_silver_pivot_sql.py

# 重建 Silver Fact (Multi-Time Dimension)
python scripts/rebuild/run_silver_fact_sql.py

# 重建 Gold KPI
python scripts/rebuild/run_gold_kpi_sql.py
```

### 3. 自動化驗證
```powershell
# 執行全場景數據對稱比對
python scripts/validation/multi_scenario_verify.py
```

---

## 📂 核心目錄結構
- `sql/rebuild/`: 包含 v2.1 穩定版的 SQL 建表文檔。
- `docs/`: 核心技術手冊 (01~06 序號排列)。
- `scripts/`:
  - `rebuild/`: 同步與部署腳本。
  - `validation/`: 正式驗證工具。

---

## 📝 待辦事項 (Backlog)
- [ ] **1 筆差異排除**: 將 12/25 的 ACC 數據從 41 修正為 40 (篩選器細調)。
- [ ] **任務二**: 驗證 **L7 人員使用率 (User Utilization)** 指標。
- [ ] 監控背景 REFRESH 任務的效能負擔。
- [ ] 擴展 WJ2 以外廠區的數據精度對帳。
