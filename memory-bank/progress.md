# 專案進度 (Progress)

## 項目概述
DMP Flowable L5 數據流水線遷移轉換，由 V2 (Silver DISTINCT) 升級至 V3 (Gold Bitmap) 架構，旨在解決數據膨脹問題並實現 100% 報表一致性。

## 已完成里程碑 (Milestones)

### 2026-04-21: V3 Bitmap 架構正式上線 (穩定版 V3.2)
- **核心遷移**: 物理表結構全面切換為 `AggregateFunction(groupBitmap, UInt64)`。
- **數據對齊**: 達成 W51 (31筆) 與 W52 (46筆) 的 100% 報表同步。
- **技術文件正式化 (v4.0)**: 
    - 完成交付規格式的 TDD (Technical Design Document)。
    - 合併所有核心 SQL 與效能基準壓測報告。
    - 實作「如何新增指標」的 6 步驟開發 SOP。
    - 建立全目錄（Architecture/Metrics/Monitoring）網狀連結。

### 2026-04-24: Superset 儀表板穩定化與效能優化
- **解決轉型報錯**: 透過 String-based filtering 徹底解決 ClickHouse 24.3 對 ISO 格式的相容性問題。
- **立竿見影的優化**: 新增 `DimMfgFilter` 專用選單資料集，將 Dashboard 下拉選單響應速度從 **>60s 降低至 0.1s**。
- **跨時段報表穩定**: 實作 Anchor Date (基準日期) 聯動邏輯，穩定實現「7天 trending + 3週對比 + 1個月累積」的單一視圖。

### 2026-04-28: V4.2 邏輯正式上線與 UI 獨立明細表架構
- **正式上線 (Production Deployment)**: 完成 V4 同梯次邏輯的合併，執行了完整的 `--reset` 與 `--backfill`，並將 Cube.js 語意層切換為輕量直接查詢 (移除 BitmapAndnot)。
- **UI 專用明細架構**: 為了供應前端 31 欄的細緻需求 (如 `sapPlant`, `scheduleNumber` 等)，建立了一套完全獨立的明細表架構 (`silver.mv_ui_varinst_pivoted` 與 `silver.mv_fact_ui_task_details`)，成功與 KPI 運算管線解耦。
- **文件更新**: 完善了 `Metrics_and_Data_Definitions.md` 的業務定義與查帳對齊基準，並新增 `UI_Detail_Fields_Mapping.md` 指南。

### 2026-04-27: V4.2 KPI 邏輯重構 (同梯次分析模式)
- **核心轉換**: 從「快照累積」模式轉型為 **「當日開單同梯次 (Same-day Cohort) 分析」**。
- **互斥優先級**: 實作 `Done > Doing > Todo` 判定，徹底解決一筆任務在不同指標重複出現的問題。
- **100% 數據對齊**: 達成 **Todo / Doing / Acc (WIP)** 三大熱指標與 PRD UI 的完全同步。
- **工單系統對齊**: 於 Silver 層正式導入 **`315` 工單前綴** 判定規則，提升 V3 流程捕捉完整度。
- **技術修正**: 實作 `COALESCE` 空值補償，解決 NULL Claim Time 導致的數據遺漏。

## 當前狀態項目 (Status)

| 模組 | 狀態 | 備註 |
| :--- | :--- | :--- |
| **Gold Layer ETL** | ✅ V4.2 | 已完成同梯次活動分析邏輯重構並正式上線 |
| **UI Detail Layer** | ✅ 已建立 | 建立獨立的 31 欄寬表供前端使用，與 KPI 管線解耦 |
| **技術文件 (TDD)** | ✅ 最新版 | 業務指標與前端對照文件已同步更新 |
| **Cube.js Model** | ✅ V4.2 | 移除複雜交集，完全對接互斥的 V4 指標 |
| **Superset Dashboard** | ✅ 運作中 | 達成 0.1s 選單響應與 11-period 視圖 |

## 待辦事項 (Todo)
- [x] 完成 V4.2 同梯次邏輯合併與 Cube 整合。
- [x] 建立前端 UI 專屬明細寬表。
- [ ] 建立自動化回填 (Backfill) 監控機制。
- [ ] 實作 L7 人員利用率數據管線。
