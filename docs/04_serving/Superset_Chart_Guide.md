# L5 專案完成度與 Superset 定義總表 (V3.2)

> **版本說明**：本文件最後更新 **2026-04-24**，已全面對齊 **Bitmap V3 聚合架構** 與 **DimMfgFilter 輕量選單模式**。

---

## 1. 核心指標與架構更新 (Core Framework)

截至 2026-04-24，系統已升級至 **Bitmap V3 性能版**，顯著提升大數據量下的 `Acc (在途)` 與 `Unique Task Count` 計算精準度。

| 項目 (Component) | 狀態 | 說明 (Details) |
| :--- | :--- | :--- |
| **指標引擎 (KPI)** | ✅ **Bitmap V3** | 採用 ClickHouse Bitmap 運算，徹底解決「跨天 ID 重複加總」導致的數據偏大問題。 |
| **選單效能** | ✅ **0.1s 響應** | 透過 `DimMfgFilter.js` 獨立選單模型，解決原本篩選選單 Loading 超過 60 秒導致的 Network Error。 |
| **日期處理** | ✅ **String-Link** | 轉換為 `YYYY-MM-DD` 10 位字串比對，解決 ClickHouse 24.3 在 ISO 時間字串轉型上的報錯。 |
| **報表跨度** | ✅ **11 週期** | 選取任一基準日，系統自動顯示：**7 天趨勢 + 3 週對比 + 1 個月加總**。 |

---

## 2. Superset 關鍵維度定義 (Dimensions Mapping)

在設定圖表或篩選器時，請務必區分以下兩個日期維度的不同用途。

| 維度名稱 (Superset Label) | Cube 欄位名 (Field) | 關鍵用途 (Usage) |
| :--- | :--- | :--- |
| **日期篩選 (基準日期)** | `snapshotDate` | **所有篩選器的目標！** 用於決定「時光機」要看哪一天。所有報表行共享同一個值。 |
| **實際快照日期** | `realSnapshotDate` | **僅用於展示**。代表該筆數據來自哪一天的快照 (例如 7 天趨勢中的每一天)。 |
| **地區/廠區/線體 (diff)** | `diffRegion` 等 | 帶有 `diff` 前綴，專用於跨 Dataset 篩選聯動。 |

---

## 3. 圖表設定指南 (Chart Step-by-Step)

### A. L5 任務完成率趨勢圖 (V3 Line/Mixed)
**用途**: 每日/每週運營監控，查看任務趨勢與完成率。

| 設定項 (Setting) | 值 (Value) | 備註 |
| :--- | :--- | :--- |
| **Dataset** | `L5TaskPeriodic` | 最新 V3 穩定版 |
| **X-Axis** | `periodName` (週期/日期名) | 顯示 W1, Jan., 2026-01-08 等 |
| **Sort By** | `periodSortOrder` | 必須選 **Ascending** (升冪) 以確保日期排序正確 |
| **Metrics** | `doneRate` (完成率), `totalQty` | 使用 Bitmap 運算後之百分比 |

### B. L5 任務明細狀態表 (V3 Pivot Table)
**用途**: 結合 Pivot 結構，查看各地區、各階段(Todo/Doing/Done)的詳細任務分佈。

| 設定項 (Setting) | 值 (Value) | 備註 |
| :--- | :--- | :--- |
| **Dataset** | `L5TaskPeriodicPivot` | 專為表格優化之長表模型 |
| **Rows** | `diffRegion`, `diffPlant`, `statusName` | 階層式堆疊展示 |
| **Metrics** | `taskQty` (任務量), `taskPct` (%) | |
| **Filtering** | 必須對準 `snapshotDate` | 確保 11 個週期資料完整跳出 |

---

## 4. Dashboard 篩選器配置 (Native Filters)

為了解決效能與連動問題，請遵循以下配置 SOP：

1.  **資料來源選取**：
    *   所有篩選器（地區、廠區、日期等）的 **「Filter Value Source (Dataset)」** 務必選擇 `DimMfgFilter`。
2.  **日期篩選器對應 (Mapping)**：
    *   將 Date 篩選器的目標對準所有 Dataset 的 **`snapshotDate` (日期篩選/基準日期)**。
    *   **⚠️ 警告**：切勿對準 `realSnapshotDate`，否則選取日期後歷史資料會被篩除。
3.  **排序優化**：
    *   在日期篩選器內設定 `Sort: DESC`，確保選單最上方顯示的是最新的日期。

---

## 5. 常見問題排除 (Troubleshooting)

### Q: 為什麼點了日期後，圖表突然縮到只剩下一個點？
*   **原因**：篩選器對準了 `實際快照日期` 而非 `日期篩選(基準日期)`。
*   **解法**：修改 Dashboard 篩選器設定，將 Mapping 目標改回 `snapshotDate`。

### Q: 為什麼選單裡看不到最新的日期？
*   **原因**：Dataset 欄位未同步或排序未更新。
*   **解法**：在 Dataset 頁面點擊 **"Sync columns from source"** 並確保 `DimMfgFilter` 的 SQL 包含 `ORDER BY snapshot_date DESC`。

### Q: 選取日期時出現 Arrow error: Cannot convert string to type DateTime?
*   **原因**：Clickhouse 24.3 與 ISO 時間格式不相容。
*   **解法**：確認 Cube 定義中使用的是 `type: string` 搭配 `YYYY-MM-DD` 格式（目前 V3 已全量修復）。
