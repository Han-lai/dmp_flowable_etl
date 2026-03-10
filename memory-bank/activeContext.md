# 當前工作脈絡 (Active Context)

**最後更新**: 2026-03-10

---

## 🎯 當前焦點 (Current Focus)

### ⏸️ 待處理問題 (Pending)
- **L7 User Utilization (Deferred)**: User requested to defer the fix for `gold.rmv_user_utilization` (currently empty/dropped) and its validation.
- **L7 Logic Discrepancy**: Nov & Dec analysis shows need for strict "5 conditions" validation when resumed.

### 核心任務
- **Vx 歸屬邏輯修復 (廠區與特權工單優先規則)**: 【已解決】修正了 `04_silver_fact_tasks` 的 `vx_type` 判斷順序。將 DG3 與 NPE 廠區專屬的特權工單 (如 196, 315) 的判斷層級提升至 `TASK_DEF_KEY_` 之上，成功解決了 V1 資料被誤判為 V3 導致掛零的問題。
- **異廠同名線段歸屬修復 (MDM Join Bug)**: 【已解決】修復了 DG3 廠區 ST02 等線段被錯誤歸類至 CNE (華東) 的問題。原因為底層 MDM 有多廠 (DG3, WJ5) 共用同一個線體名稱。Silver 層改採 `LineName + PlantCode` 雙主鍵進行轉換與去重，已成功讓資料在 Superset 正確呈現於 CNS。
- **Cube Model 架構優化**: 已完成高品質系列模型修正 (ACC Rate Logic Fix) 與文件同步。
- **L5 Insight API (FastAPI) 正式版**: 【已完成】實作了 `/api/l5/task-report` 並移除所有 `v2` 標記。支援 GET/POST 複雜報表格式，並完成 Docker 全域文件同步。
- **服務架構分離 (Split-Stack)**: 【已完成】將 ClickHouse 與 API 拆分為獨立堆疊，支援獨立生命週期管理。
- **動態掛載部署 (Dynamic Runtime)**: 【已完成】API 採用 Volume-mount 模式掛載 `main.py`，支援透過 FileBrowser 即修即用，大幅優化運維效率。

## 進行中的工作 (2026-03-10)

- **VM 部署驗證 (Port 7088)**: 使用者正在 VM 環境中測試新版 `docker-compose-api.yml` 與 FileBrowser 代碼修改機制。
- **Swagger UI 功能與數據查核**: 驗證 `/api/l5/task-report` 在真實數據下的產出準確性。

### ClickHouse 雙產線效能驗證與監控補齊 (2026-03-06) ✅ 已完成
- **壓測成果**: 兩產線 P50 查詢延遲均 < 0.9s，達成吞吐與延遲指標，壓縮比達 6.6 倍，無記憶體與 CPU 瓶頸。
- **文件產出**: 新增 `benchmark_result.md` (Raw)、`benchmark_briefing.md` (口語重點)、`benchmark_runbook.md` (操作 SOP) 與 `dashboard_usage_guide.md`。
- **監控面板**: 新增含 QPS、Latency 分佈與資料壓縮比等 4 組基準測試衍生面板。

### L5 併發效能壓力測試 (2026-03-05) ✅ 已完成
- **成果**: 使用 `clickhouse-benchmark` 完成三回合壓測，10 人併發 × 100 次查詢。
- **關鍵數據**: Round 1 QPS=411.8 | Round 2 (Cube.js) QPS=87.4, P95=173ms | Round 3 (全域掃描) QPS=70.0, P95=177ms
- **腳本**: `stress_test_l5_benchmark.py` (單廠), `stress_test_l5_global.py` (全域)

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
```
