# 專案進度 - DMP Flowable

## 已完成里程碑
 
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

### 2026-02-03
- ✅ 恢復 `VARINST` 資料同步 (17.3M 筆, finish at 2026-01-08)
- ✅ 恢復 `TASKINST` 資料同步 (1.48M 筆, finish at 2026-01-08)
- ✅ 驗證 `Silver Layer (mv_fact_task_vx)` 資料正確注入 (1.49M 筆)
- ✅ 清理 4 個過期衝突的 Silver MViews (`mv_fact_task_vx_attribution_*`)，修復 `UNKNOWN_IDENTIFIER` 錯誤
- ✅ `PROCINST` 資料同步 (完成, Snapshot 0108)
- ✅ 修復 `silver.mv_fact_task_vx` MVIEW 定義 (移除 Alias 避免解析錯誤)
- ✅ 實作 Sync Script (`sync_batches_consolidated.py`) 的自動重試與批次縮小機制 (4小時)

### 2026-01-29
- ✅ 完成資料同步驗證
- ✅ Data Pipeline 架構重建 (sql/rebuild)

### 2026-01-15 (之前)
- ✅ Bronze 層 18 張表同步完成
- ✅ Silver 層 4 張 RMV 建立完成
- ✅ Gold 層 2 張 RMV 建立完成
- ✅ Cube.js 語意層 API 完成
- ✅ 11 個指標與 Benchmark 邏輯等價驗證

## 暫緩項目
- ⏸️ 逾期在途業務事件數 (缺 HealthSettings 表)
- ⏸️ 自動化排程 (目前手動執行)

- [ ] 驗證 L7 人員使用率 (User Utilization) 指標
- [ ] 監控定時刷新 (REFRESH EVERY 1 HOUR) 的資源消耗
- [ ] 擴展其他廠區的 L5 指標對帳


