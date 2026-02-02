# 專案進度 - DMP Flowable

## 已完成里程碑

### 2026-01-30
- ✅ L5 指標驗證完成 (Gold 層 vs QAS SQL)
- ✅ 確認 VxType 歸屬邏輯已在 Silver 層實作
- ✅ 確認 Region 維度已透過 MDM 補齊
- ✅ 發現數據差異 (198 vs 180)，初步分析為時間篩選邏輯差異
- ✅ 建立 memory-bank 目錄結構
- ✅ **技術文件更新 (Rebuild 版)**
  - `ARCHITECTURE_OVERVIEW.md` - 新建架構總覽
  - `silver_mviews_architecture.md` - 更新為 3 張 MVIEW
  - `data_pipeline_diagram.md` - 更新為單路徑 + Refreshable MView

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

## 待確認
- ❓ 是否需要調整 Gold 層時間篩選邏輯與 QAS 一致？
