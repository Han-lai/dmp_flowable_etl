# CLAUDE.md - DMP Flowable 快速上手指南 (Quick Start)

> [!IMPORTANT]
> **Git Push**: 接下來的任務都不要自動地幫我 push 到 GitHub 當中。 (No automatic pushing to GitHub.)

- **維度標準化**: 完成「五階維度」與「組織名稱（廠區）」的最終對齊與繁體化。
- **數據準確**: 完成 12/25 WJ2/E5 數據完全對齊 (ACC=40)，並驗證 CNS DG3 廠區數據路徑。


---

## 專案狀態: V4.4 (Phase 4 Pre-Aggregation & Windowing Fix)
- **Phase 4 預聚合部署**: 捨棄 Cube.js 語意層的 Bitmap 即時運算，改為 ETL 階段預聚合 (Gold `rmv_l5_task_summary`)，前端查詢降級為單純的 `sum(qty)`。時間與空間複雜度從 O(N²) 降為 O(1)，單一指標查詢由 30~40 秒降至 1.5 秒 ~ 8.5 秒。
- **增量 ETL 視窗修復**: 修正了 Incremental ETL (`backfill_gold_summary.sql`) 在聚合 `Week` 與 `Month` 時遺失歷史資料 (ACC) 的重大缺陷，透過動態邊界 `toStartOfWeek` 與 `toStartOfMonth` 確保資料正確，已完成 6 萬筆歷史聚合資料回填。
- **連線配置**: 正式 ClickHouse 伺服器 `REDACTED_IP:8123 (default / <CLICKHOUSE_PASSWORD>)`。

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
