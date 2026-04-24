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

## 當前狀態項目 (Status)

| 模組 | 狀態 | 備註 |
| :--- | :--- | :--- |
| **Gold Layer ETL** | ✅ 已部署 | 支援 Daily/Weekly/Monthly 預聚合位圖 |
| **技術文件 (TDD)** | ✅ v4.0 | 已完成 Final Fusion 與深度聯結 |
| **Cube.js Model** | ✅ 已優化 | 已完成 V3.2 穩定版，解決轉型與過濾器鎖定問題 |
| **Superset Dashboard** | ✅ 已穩定 | 達成 0.1s 選單響應與 11-period 視圖 |
| **W1 (跨年週) 對齊** | ✅ 達成 | 已完成 100% 數據對齊 |

## 待辦事項 (Todo)
- [x] 修正 `cube_l5_task_periodic.js` 的週/月報表取值為「期末快照」而非「期間聯集」。
- [x] 驗證 W1 跨年週數據 (NBU/E5 12 筆目標)。
- [x] 解決 ClickHouse 24.3 與 Superset ISO Date 的轉型相容性問題。
- [ ] 建立自動化回填 (Backfill) 監控機制。
- [ ] 實作 L7 人員利用率數據管線。
