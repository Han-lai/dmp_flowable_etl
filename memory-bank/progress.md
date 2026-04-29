# 專案進度 (Progress)

## 項目概述
DMP Flowable L5 數據流水線遷移轉換，由 V2 (Silver DISTINCT) 升級至 V4.3 (Super Silver) 架構，旨在建立高品質、高精確度的統一任務事實表，達成 KPI 指標與 UI 明細的 100% 同步。

## 已完成里程碑 (Milestones)

### 2026-04-29: V4.3 超級事實表大統一 (Super Silver Architecture)
- **架構整合**: 成功將「UI 明細 V2」的功能（L4 編號、11 個業務變數、時效指標）合併回核心事實表 `silver.mv_fact_task_vx`。
- **資料精確度優化**: 
    - 實作了 **`argMax` 去重關聯**，解決了 `LEFT JOIN` 變數表時產生的資料虛胖問題，數據精度與目標 100% 吻合。
    - 修正了 **315** 工單分類邏輯。
- **專案清理**: 移除所有過時的測試 DML 與 Schema 檔案，完成 ETL 資料夾與管線邏輯的標準化。
- **語義層對接**: 建立 `L5TaskDetailsSuper` Cube，正式支援前端明細鑽取。

### 2026-04-29: V4.2 終極版 - 跨年週對帳與週期感知優化
- **100% 數據對齊**: 成功解決 CNE WJ2 NBU E5 W1 的對帳落差，達成 TODO: 12 / DONE: 440 的原始對齊。
- **週期感知 (Period-Aware) 邏輯**: 在 Cube.js 語意層實作自動邊界補齊，解決跨年週期數據被切斷的問題。
- **全量數據回填**: 完成 2025-09 至 2026-01 的歷史回填，確保資料與 2025 年末的業務週期完全接軌。

### 2026-04-28: 多粒度梯次 (Multi-Granularity Cohort) 正式上線
- **指標定義升級**: 實現了「週期結算」邏輯，讓週/月報表能反映任務在週期結束時的真實狀態。
- **架構優化**: 在 Gold 層導入多粒度 Bitmap 欄位 (`daily`, `weekly`, `monthly`)。

## 當前狀態項目 (Status)

| 模組 | 狀態 | 備註 |
| :--- | :--- | :--- |
| **Silver Fact Layer** | ✅ V4.3 | 超級事實表 (Super Silver)，包含 L4、業務變數與時效 |
| **Gold Layer ETL** | ✅ V4.2 | 支援週期感知 (Period-Aware) 與多粒度 Bitmap |
| **DML 效能** | ✅ 已優化 | 實作 argMax 去重，確保 JOIN 後不產生重複數據 |
| **ETL 檔案清理** | ✅ 已完成 | 僅保留 `execute_etl.py` 與核心 SQL 模板 |
| **Cube.js Model** | ✅ V4.3 | 新增 `L5TaskDetailsSuper` 用於正式明細鑽取 |

## 待辦事項 (Todo)
- [x] 解決 W1 跨年數據對帳落差。
- [x] **將 UI 明細邏輯整合進核心 Fact Table (V4.3 升級)**。
- [x] **實作 DML argMax 去重優化，解決資料重複問題**。
- [x] **清理過時 ETL 程式碼與檔案**。
- [ ] 提交並推送所有 V4.3 邏輯變更至版本控制。
- [ ] 觀察 Super Silver 表在前端 Superset 的明細鑽取效能。
