# 當前工作脈絡 (Active Context)

**最後更新**: 2026-04-07

---

## 🎯 當前焦點 (Current Focus)

### ⏩ 進行中
- **性能監控**: 觀察 Silver/Gold 全面重建後的產線數據加載速度。
- **文件維護**: 持續優化 ODBC 版技術文件中的圖表與範例代碼。

### ✅ 近期已解決
- **文件雙軌化 (Dual-Layering)**: 完成 `docs/` 資料夾整理，建立 `legacy/` 存檔 JDBC 舊版文件，並將 ODBC 文件提升為標準命名的現行文件。
- **ODBC 技術文件精進**: 建立 `02_ClickHouse_ODBC_Setup.md` 與更新 v5.0 架構總覽，全面對應現行 Python 同步機制。
- **Silver/Gold 全面重建**: 完成 2025-01-01 至今的完整資料 Backfill。
- **SQL 關鍵修復**: 解決 `backfill_silver.sql` 別名衝突與 HR `EmpName` 缺失問題。
- **ODBC 管線遷移**: 成功棄用 JDBC Bridge，改採原生 ODBC 驅動。
- **L5 指標 OOM 危機**: 已透過 `ReplacingMergeTree` 與 `ARRAY JOIN` 優化解決。

### ClickHouse 雙產線效能驗證與監控補齊 (2026-03-06) ✅ 已完成
- **壓測成果**: 兩產線 P50 查詢延遲均 < 0.9s，達成吞吐與延遲指標，壓縮比達 6.6 倍，無記憶體與 CPU 瓶頸。

### Cube Model 歸檔與簡化 (2026-02-10)
- **模型精簡**: 將 7 個 Cube 模型精簡至 2 個，歸檔 5 個舊版模型至 `archive/` 目錄
- **保留模型**: 僅保留高品質系列 (`cube_l5_task_periodic_v2.js` 和 `cube_l5_task_periodic_v2_pivot.js`)
- **文件更新**: 更新 README 說明當前使用的模型與歸檔狀態
- **效益**: 減少 71% 維護負擔，統一使用標準進階邏輯

### Gold Layer Recovery (2026-02-13)
- **View Migration**: `gold.rmv_l5_task_completion` -> `gold.rmv_l5_task_completion_v2`.
- **Data Gap Fixed**: Backfilled `DG3/SMT/ST02` data (176 rows).
- **Cube Synced**: All active models updated to standard.

## ⚠️ 重要開發規範 (IMPORTANT)
> [!IMPORTANT]
> **Git Push**: 禁止在任務中自動執行 `git push`。所有變更應由使用者手動審核後推送。 (No automatic pushing to GitHub.)

## 🎯 專案當前狀態 (2026-02-10 UPDATE)
- **7天滾動分母實作**: 徹底解決週末 Acc Rate 暴飆問題，達成日、週、月指標邏輯的一致。
- **V2 模型魯棒性增強**: 通過 Triple-OR 篩選邏輯，解決了 Superset 不同模式（Dashboard vs Chart）下的時間格式轉換錯誤。
- **資料核對**: 完成 CNS DG3 SV (SMT) S06 線體的資料路徑驗證與核實。

### Logic Fixes
- [x] L5 Insight API (GET/POST Implementation)
- [x] API Service Separation (Split-Stack Architecture)
- [x] L5 Standard Pivot Cube Model (Implemented & Documented)
- [x] ACC Rate Calculation (Cube-only Rolling Logic approved)
- [x] Vx Attribution Priority (Updated Spec to match Code: Key > Mo)
- [x] Gold MView Rebuild Logic (Added Sleep for Consistency)

### Verification
- [x] QAS WJ2/NBU Verification (Zero V1 tasks found)
- [x] QAS DG3/SMT Verification (V1 tasks exist but belong to NPE, not SMT)
- [x] L5 Gold Dimensions Verification (Region/Plant populated)

### L5 週期性報表與視覺化 (2026-02-06)
- **Superset 雙軸圖表整合**: 成功解決混合圖表 (Bar + Line) 的排序與雙軸顯示問題。

## ⚙️ 開發規範 (Development Rules)
- **Git Push**: 接下來的任務都不要自動地幫我 push 到 GitHub 當中。 (No automatic pushing to GitHub in subsequent tasks.)

## 待辦事項
- [x] 完成 L5 指標三方對齊驗證 (WJ2/E5: 192)
- [x] 成功修復並實施 Refreshable Pivot 架構
- [x] 完成 100+ 腳本與 12+ 文件之清理與歸檔
- [x] L5 指標業務邏輯深度校正 (Attribution, Snapshot, Acc)
- [x] L5 Gold 維度修復 (Race Condition Fix)
- [x] Cube.js 週期性報表 X 軸自動排序支援
- [ ] 任務二：驗證 L7 人員使用率 (User Utilization) 指標 (暫緩)
- [ ] 監控全自動刷新定時器的資源消耗
