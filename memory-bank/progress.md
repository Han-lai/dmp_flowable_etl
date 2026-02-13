# 專案進度 - DMP Flowable

## 已完成里程碑
 
### 2026-02-10 (今日進度)
- ⚠️ **發現 V2 Pivot 模型 ACC Rate 計算錯誤**:
    - **問題**: `cube_l5_task_periodic_v2_pivot.js` 在 Pivot 轉換時遺漏了 `acc_total_qty` 欄位
    - **影響**: ACC Rate 使用錯誤的分母 (`total_qty` 而非 7天滾動總量),導致 2025-12-28 等日期出現異常大的比率
    - **根源**: 第 161 行使用 `total_qty` 作為分母,應使用 `acc_total_qty`
    - **狀態**: 已建立修正計劃 (`implementation_plan.md`),待明日實作

### 2026-02-10 (今日進度 - 早期)
- ✅ **Cube Model 架構優化與歸檔**:
    - **模型精簡**: 將 7 個 Cube 模型精簡至 2 個 (減少 71% 維護負擔)
    - **歸檔清單**: 移動 5 個舊版模型至 `cube/model/cubes/archive/`:
        - `cube_gold_l5_task_completion.js` (舊版 Gold 層模型)
        - `cube_l5_dashboard_summary.js` (舊版 Dashboard 模型)
        - `cube_l5_task_completion.js` (舊版 Pivot 模型)
        - `cube_l5_task_periodic.js` (V1 週期性報表)
        - `cube_user_utilization.js` (用戶利用率模型)
    - **保留模型**: 僅保留 V2 系列
        - `cube_l5_task_periodic_v2.js` (週期性報表，支援 7 天滾動分母)
        - `cube_l5_task_periodic_v2_pivot.js` (狀態比較報表，支援歷史查詢)
    - **文件更新**: 更新 `README_L5_DASHBOARD_CUBE.md` 說明當前架構
    - **效益**: 統一使用 V2 進階邏輯，簡化維護流程

## 進行中的工作

### 2026-02-11
- ✅ **V2 Pivot ACC Rate 計算修復**:
    - **修正**: 在 `cube_l5_task_periodic_v2_pivot.js` 中補回 Month/Week 的 `acc_total_qty` 欄位
    - **驗證**: 確保 Day 粒度使用 7天滾動總量，Month/Week 使用週期總量作為分母
    - **交付**: 提供 Python 驗證腳本 `scripts/validation/verify_gold_acc.py` 供用戶自行核對 Gold 層數據

- ✅ **2026-02-11**:
    - **Documentation**: Overhauled `PROJECT_AUDIT_REPORT.md`, clarified ACC logic, removing L7.
    - **QAS Verification**:
        - Confirmed **Zero** V1 tasks in `WJ2/NBU` scope (QAS Env).
        - Confirmed V1 tasks in `DG3` belong to `NPE`, not `SMT`.
        - Verified standard SQL for `WJ2/NBU/E5` (Count: 184) and `DG3/SMT/ST02` (Count: 3636).
    - **Spec Compliance**:
        - Updated Vx Attribution Priority in Spec to match Code (`Key > Mo`).
        - Added warning about missing variables (Region/Line) in QAS data.
    - **Feature**: Removed L7 User Utilization from active scope.
    - **架構校正**: 重寫 `PROJECT_AUDIT_REPORT.md` 的 End-to-End Table Mapping，補齊 Bronze/Silver/Gold 完整流向。
    - **邏輯釐清**: 明確定義 ACC Rate 在 Daily (Rolling) 與 Week/Month (Fixed Period) 的計算差異。
    - **術語優化**: 將「期末快照」與「轉結水位」白話化為「期末狀態」與「未完成積壓」。
    - **L7 移除**: 應要求暫時移除 L7 人員使用率相關內容，聚焦於 L5 指標。
    - **模型簡化**: 明確標記舊版 Pivot 模型為 Deprecated，僅保留 V2 Standard 與 V2 Pivot。

### 2026-02-10 (昨日進度)
- ✅ **L5 Acc Rate 指標邏輯修正**:
    - **核心問題**: 解決週末/連假期間因當日活動量 (`total_task`) 驟減導致 Acc Rate 暴飆 (如 12/28 達 418%) 的問題。
    - **解決方案**: 
        - **日報表**: 引入「7天滾動總量」作為分母，平滑波動，確保 12/28 數據準核對齊為 7%。
        - **週/月報表**: 自動採用週期內的總量作為分母。
- ✅ **L5 週期報表模型 (V2) 最終穩定化**:
    - **技術突破**: 解決 Superset Chart 傳送帶有微秒的 Timestamp (`.000000`) 導致的「Cannot convert string to Date」轉換錯誤。
    - **魯棒性優化**: 實作 `params` CTE 的 **Triple-OR 篩選邏輯**。透過「字串對字串」比對技術，全方位支持 Dashboard 與 Chart 的不同時間篩選格式。
    - **UI 優化**: 修正五階維度名稱 (如「廠區」字樣) 與排序邏輯。
- ✅ **CNS DG3 資料核帳**: 協助用戶確認 CNS DG3 廠區的線體對應關係（S06 對應 ST06），並驗證 12/31 數據準確性。

### 2026-02-06
- ✅ **L5 週期報表架構優化 (Refactoring)**:
    - **Phase 1 (SQL Standard)**: 建立 `sql/rebuild/dynamic_periodic_report.sql`，採用「參數推論 (Inference)」邏輯，自動依據日期範圍判斷當月/歷史模式，解除對 Superset Jinja 的依賴。
    - **Phase 2 (Cube V2)**: 實作新模型 `cube_l5_task_periodic_v2.js`，將所有運算邏輯下沉至 SQL CTE，Cube 僅負責 Schema Mapping，大幅減輕維護負擔。
- ✅ **L5 週期報表架構優化 (Refactoring)**:
    - **Phase 1 (SQL Standard)**: 完成 `sql/rebuild/dynamic_periodic_report.sql` 標準化，改採參數推論邏輯 (Inference Logic)。
    - **Phase 2 (Cube V2)**: 成功部署 `cube_l5_task_periodic_v2.js`，實現 Logic Push-down 架構。
    - **關鍵技術突破**: 解決 View Predicate Pushdown 失效問題，改用 Cube SQL Injection + Filter Separation 技術，實現「時光機 (Time Machine)」任意日期回溯與「8天滑動視窗」顯示。
- ✅ **L5 週期報表架構優化 (Refactoring - V2 Final)**:
    - **Phase 1 (SQL Standard)**: 邏輯 100% 下沉至 Clickhouse，解除對 BI 工具特定語法的依賴。
    - **Phase 2 (Cube V2)**: 實現「時光機 (Time Machine)」架喚，透過 Filter-Display 分離技術突破日期篩選限制。
    - **Phase 3 (Superset Integration)**: 解決 Dashboard 帶入 ISO Timestamp 的類型轉換錯誤，達成「選一天看全週」的穩定功能。
- ✅ **L5 週期性報表完成 (Stable Dual-Axis)**:
    - 成功實作 Superset 混合圖表 (Mixed Chart) 的自定義排序 (`periodSortOrder`) 與雙軸顯示 (Quantity + Rate)。
    - 完成 `cube_l5_task_periodic.js` 的穩定版開發 (Month/Week/Day 混合顯示)，確保 ClickHouse 函數相容性。
    - 建立 `docs/L5_Completion_Superset_Guide.md` 作為交付文件，記載設定參數與專案完成度。
- ✅ **L5 任務週期報表優化 (Mixed Chart Sorting)**:

### 2026-02-05
- ✅ **Gold 層架構修復 (Background Refresh Logic)**:
    - 解決 `gold.rmv_l5_task_completion` 定時刷新失敗問題 (修正 JOIN 語法為 CROSS JOIN)。
    - 資料恢復完成並與基準值對應 (Done=192, ACC=41 for 12/25)。
- ✅ **12/25 數據基準再確認**:
    - 每日任務數 (Daily Task Count) 確立為 192 筆。
    - 累積在途量 (ACC) 確立目標值為 40 筆 (目前 41 筆，1 筆差異調查中)。
- ✅ **Cube.js 模型架構分拆 (Dual-File Architecture)**:
    - `cube_l5_task_completion.js`: 保持「轉置版 (Pivoted)」，穩定支援 Superset 樞紐分析表。
    - `cube_l5_task_chart.js` [NEW]: 「寬表版 (Wide)」，專用於 Superset 混合圖表 (Mixed Chart) 與 Tooltip 百分比顯示。

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

### 2026-02-03 (Early)
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

- [x] 驗證 L7 人員使用率 (User Utilization) 指標 (因 User 要求暫緩修復)
    - [x] 針對 11、12 月份數據進行「五個條件」驗證 (嚴格 V3 邏輯)
    - [x] 核對 PowerUser 與 None Group 的排除邏輯
    - [x] 確認分母 (Config Users) 與分子 (Active Users) 定義是否符合預期
- [x] **修復**: L5 Gold MView 維度缺失問題
    - 解決方案: 於重建腳本中加入 `sleep(2)` 等待 Silver MView 刷新
    - 狀態: `gold.rmv_l5_task_completion` 已包含完整 Region/Plant/Factory/Line 資料
- [x] **決策**: ACC Rate 427% 異常修正
    - 用戶決定保留 Cube.js V2 模型中的 Rolling 7 Days 邏輯
    - Gold SQL (`rmv_l5_task_completion`) 維持每日匯總邏輯 (Status Quo)
- [x] 執行 MView 重建腳本 `scripts/rebuild/update_mviews_no_data_loss.py` 完成 (48hr 更新生效)


