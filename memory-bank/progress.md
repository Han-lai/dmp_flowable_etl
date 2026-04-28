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

### 2026-04-27: V4.2 KPI 邏輯重構 (同梯次分析模式)
- **核心轉換**: 從「快照累積」模式轉型為 **「當日開單同梯次 (Same-day Cohort) 分析」**。
- **互斥優先級**: 實作 `Done > Doing > Todo` 判定，徹底解決一筆任務在不同指標重複出現的問題。
- **100% 數據對齊**: 達成 **Todo / Doing / Acc (WIP)** 三大熱指標與 PRD UI 的完全同步。
- **工單系統對齊**: 於 Silver 層正式導入 **`315` 工單前綴** 判定規則，提升 V3 流程捕捉完整度。
- **技術修正**: 實作 `COALESCE` 空值補償，解決 NULL Claim Time 導致的數據遺漏。

## 當前狀態項目 (Status)

| 模組 | 狀態 | 備註 |
| :--- | :--- | :--- |
| **Gold Layer ETL** | ✅ V4.2 | 已完成同梯次活動分析邏輯重構 (Cohort-based) |
| **技術文件 (TDD)** | ✅ v4.2 | 已更新 V4.2 活動增量指標定義與 SQL 腳本 |
| **Cube.js Model** | ✅ 已優化 | 已完成 V3.2 穩定版，目前正評估是否將 V4.2 整合至 Cube |
| **Superset Dashboard** | ✅ 已穩定 | 達成 0.1s 選單響應與 11-period 視圖 |
| **數據一致性檢驗** | ✅ 達成 | V4.2 全面達成 Todo/Doing/Acc 與 UI 100% 同步 |

## 待辦事項 (Todo)
- [x] 修正 `cube_l5_task_periodic.js` 的週/月報表取值為「期末快照」而非「期間聯集」。
- [x] 驗證 W1 跨年週數據 (NBU/E5 12 筆目標)。
- [x] 解決 ClickHouse 24.3 與 Superset ISO Date 的轉型相容性問題。
- [ ] 建立自動化回填 (Backfill) 監控機制。
- [ ] 實作 L7 人員利用率數據管線。
