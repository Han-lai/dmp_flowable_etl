# CLAUDE.md - DMP Flowable 快速上指南 (Quick Start)

## 🎯 專案當前狀態 (2026-02-05)
本專案已完成 **Gold 層背景刷新機制修復** 與 **12/25 數據基準確認**。
- **數據基準**: 12/25 (WJ2/E5) 關鍵指標 (Todo, Doing, Acc) 與預期 **完全一致**。
- **邏輯固定**: 確立 Vx 歸屬優先級、歷史時點快照判斷、7 天滑動 Acc 視窗。
- **文件鞏固**: 定義文件 `docs/03_1_columns_defin.md` 已注入修正歷程。
- **報告產出**: 已生成 `docs/reports/L5_Periodic_Metrics_Report_20260204.md`，提供 W51-W01 及全月指標總覽。
- **已知差異**: WJ2/E5 在 12/30, 12/31 保留部分 DONE 差異 (+2/+1)，已在文件中註記。

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
