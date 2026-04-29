# CLAUDE.md - DMP Flowable 快速上手指南 (Quick Start)

> [!IMPORTANT]
> **Git Push**: 接下來的任務都不要自動地幫我 push 到 GitHub 當中。 (No automatic pushing to GitHub.)

- **維度標準化**: 完成「五階維度」與「組織名稱（廠區）」的最終對齊與繁體化。
- **數據準確**: 完成 12/25 WJ2/E5 數據完全對齊 (ACC=40)，並驗證 CNS DG3 廠區數據路徑。


---

## 專案狀態: V4.3 Final (UI Detail Optimized)
- **核心架構**: 獨立 UI 明細事實表 (`mv_fact_ui_task_details_v2`) + 週期感知 (Period-Aware) Bitmap。
- **數據進度**: 成功對齊 W1 (12/440) 數據落差，並完成 2025-09~2026-01 的 1.47M 筆明細回填。
- **關鍵改進**: 支援 L4 流程編號 (`BUSINESS_STATUS_`)、11 個業務變數、以及分鐘級時效指標。

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
# 完整重建 Bronze → Silver → Gold (KPI Layer)
python scripts/etl/execute_etl.py

# 執行 UI 明細寬表回填 (UI Layer V2)
python scripts/etl/execute_ui_v2.py --start 2025-09-01 --end 2026-01-31
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
