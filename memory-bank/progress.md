# 專案進度 (Progress)

## 項目概述
DMP Flowable L5 數據流水線遷移轉換，由 V2 (Silver DISTINCT) 升級至 V3 (Gold Bitmap) 架構，旨在解決數據膨脹問題並實現 100% 報表一致性。

## 已完成里程碑 (Milestones)

### 2026-04-21: V3 Bitmap 架構正式上線 (穩定版 V3.2)
- **核心遷移**: 物理表結構全面切換為 `AggregateFunction(groupBitmap, UInt64)`。
- **數據對齊**: 達成 W51 (31筆) 與 W52 (46筆) 的 100% 報表同步。
- **邏輯實作**:
    - **身份唯一排除法**: 實作 `bitmapAndnot` 邏輯，確保狀態不重複計數。
    - **7D Rolling 分母**: 解決了日報表在週末因任務稀少導致的比率失真。
- **架構優化**: 數據聚合下沉至 Gold Layer，Cube.js 僅負責位圖合併，查詢延遲大幅降低。

## 當前狀態項目 (Status)

| 模組 | 狀態 | 備註 |
| :--- | :--- | :--- |
| **Gold Layer ETL** | ✅ 已部署 | 支援 Daily/Weekly/Monthly 預聚合位圖 |
| **Cube.js Model** | [/] 優化中 | 正在修正週/月報表的快照聚合偏移問題 |
| **W51/W52 對齊** | ✅ 達成 | 精確度 100% |
| **W1 (跨年週) 對齊** | 🚧 診斷中 | 需排查 12 筆數據的過濾細節 |

## 待辦事項 (Todo)
- [ ] 修正 `cube_l5_task_periodic.js` 的週/月報表取值為「期末快照」而非「期間聯集」。
- [ ] 驗證 W1 跨年週數據 (NBU/E5 12 筆目標)。
- [ ] 建立自動化回填 (Backfill) 監控機制。
