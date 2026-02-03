# CLAUDE.md - DMP Flowable 快速上指南 (Quick Start)

## 🎯 專案當前狀態 (2026-02-03)
本專案已完成 **L5 指標數據對帳** 與 **架構全面穩固**。
- **數據基準**: ClickHouse 與 MSSQL (WJ2/E5) 達成 **100% 完美對齊 (192 筆)**。
- **核心架構**: 導入 `Refreshable Pivot` 解決非同步維度遺失問題。
- **文件管理**: 目錄 `docs/` 已重新編號索引 `00_INDEX.md`，清理 100+ 腳本。

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
- [ ] **任務二**: 驗證 **L7 人員使用率 (User Utilization)** 指標。
- [ ] 監控背景 REFRESH 任務的效能負擔。
- [ ] 擴展 WJ2 以外廠區的數據精度對帳。
