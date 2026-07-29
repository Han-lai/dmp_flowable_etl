# L5 Superset 看板設定指南

**文件編號**: 04-SRV-003  
**最後更新**: 2026-04-30  
**狀態**: 正式發布 (Released)  
**維護者**: AIT / Data Engineering

---

## 1. 核心元件說明 (Core Components)

本看板由三個 Cube 模型協同運作：

> **架構異動（2026-06-16）**：`DimMfgFilter` 篩選選單模型（`cube_dim_mfg_filter.js`）已廢棄移除。篩選器資料來源請改用 `L5TaskPeriodic` 或靜態 SQL Dataset。

| Cube 模型 | 用途 |
| :--- | :--- |
| **`L5TaskPeriodic`** | KPI 主模型。提供日/週/月三種粒度的 Todo/Doing/Done 聚合指標。 |
| **`L5TaskPeriodicPivot`** | 表格專用。提供長表格式，適合 Pivot Table 及地區/廠別階層展示。 |
| **`L5TaskDetails`** | 明細下鑽模型。提供單一工單層級的任務明細查詢。 |

### 1.1 系統功能現況

| 項目 | 狀態 | 說明 |
| :--- | :--- | :--- |
| **指標引擎** | ✅ **Bitmap 高效聚合** | 採用 ClickHouse Bitmap 運算，徹底解決「跨天 ID 重複加總」的數據偏大問題。 |
| **多時間粒度** | ✅ **日 / 週 / 月** | 三種粒度各自預計算 Bitmap，查詢速度達秒級響應。 |
| **篩選選單效能** | ⚠️ **架構調整中** | 原 `DimMfgFilter` 獨立選單模型已於 2026-06-16 移除；篩選器改由 `L5TaskPeriodic` 維度欄位或靜態 SQL Dataset 提供。 |
| **日期處理** | ✅ **字串比對** | 轉換為 `YYYY-MM-DD` 10 位字串，解決 ClickHouse 24.3 ISO 時間字串轉型報錯。 |
| **明細下鑽** | ✅ **L5TaskDetails** | 支援從 KPI 圖表下鑽至單一工單明細清單。 |

---

## 2. 關鍵維度定義 (Dimensions Mapping)

在設定圖表或篩選器時，請務必區分以下兩個日期維度的不同用途。

| 維度名稱 (Superset Label) | Cube 欄位名 (Field) | 關鍵用途 |
| :--- | :--- | :--- |
| **日期篩選 (基準日期)** | `snapshotDate` | **所有篩選器的目標！** 用於決定「時光機」要看哪一天。所有報表行共享同一個值。 |
| **實際快照日期** | `realSnapshotDate` | **僅用於展示**。代表該筆數據來自哪一天的快照 (例如 7 天趨勢中的每一天)。 |
| **地區/廠區/線體 (diff)** | `diffRegion` 等 | 帶有 `diff` 前綴，專用於跨 Dataset 篩選聯動。 |

---

## 3. 圖表設定指南 (Chart Step-by-Step)

### A. L5 任務完成率趨勢圖 (Line / Mixed Chart)
**用途**: 每日/每週運營監控，查看任務趨勢與完成率。

| 設定項 | 值 | 備註 |
| :--- | :--- | :--- |
| **Dataset** | `L5TaskPeriodic` | KPI 主模型 |
| **X-Axis** | `periodName` (週期/日期名) | 顯示 W1, Jan., 2026-01-08 等 |
| **Sort By** | `periodSortOrder` | 必須選 **Ascending** (升冪) 以確保日期排序正確 |
| **Metrics** | `doneRate` (完成率), `totalQty` | 使用 Bitmap 運算後之百分比 |

### B. L5 任務明細狀態表 (Pivot Table)
**用途**: 結合 Pivot 結構，查看各地區、各階段 (Todo/Doing/Done) 的詳細任務分佈。

| 設定項 | 值 | 備註 |
| :--- | :--- | :--- |
| **Dataset** | `L5TaskPeriodicPivot` | 專為表格優化之長表模型 |
| **Rows** | `diffRegion`, `diffPlant`, `statusName` | 階層式堆疊展示 |
| **Metrics** | `taskQty` (任務量), `taskPct` (%) | |
| **Filtering** | 必須對準 `snapshotDate` | 確保 11 個週期資料完整呈現 |

### C. L5 任務明細下鑽表 (Table Chart)
**用途**: 顯示單一廠線在特定日期區間內的所有工單明細，可與上方 KPI 圖表聯動。

| 設定項 | 值 | 備註 |
| :--- | :--- | :--- |
| **Dataset** | `L5TaskDetails` | 明細下鑽模型 |
| **Columns** | `taskId`, `moNumber`, `taskName`, `statusDaily`, `taskStartDate`, `taskEndDate` | 依業務需求選擇 |
| **Filtering** | 使用 `taskStartDate` 進行日期篩選 | 對應開單日期範圍 |
| **Sort By** | `taskStartDate DESC` | 最新任務優先顯示 |

---

## 4. Dashboard 篩選器配置 (Native Filters)

請遵循以下配置 SOP：

1.  **資料來源選取**：所有篩選器（地區、廠區、日期等）的 **「Filter Value Source (Dataset)」** 選擇 `L5TaskPeriodic`（原 `DimMfgFilter` 已於 2026-06-16 移除）。
2.  **日期篩選器對應 (Mapping)**：將 Date 篩選器的目標對準所有 Dataset 的 **`snapshotDate` (日期篩選/基準日期)**。
    > ⚠️ **警告**：切勿對準 `realSnapshotDate`，否則選取日期後歷史資料會被篩除。
3.  **排序優化**：在日期篩選器內設定 `Sort: DESC`，確保選單最上方顯示最新的日期。

---

## 5. 常見問題排除 (Troubleshooting)

### Q: 為什麼點了日期後，圖表突然縮到只剩下一個點？
*   **原因**：篩選器對準了 `實際快照日期` 而非 `日期篩選(基準日期)`。
*   **解法**：修改 Dashboard 篩選器設定，將 Mapping 目標改回 `snapshotDate`。

### Q: 為什麼選單裡看不到最新的日期？
*   **原因**：Dataset 欄位未同步或排序未更新。
*   **解法**：在 Dataset 頁面點擊 **"Sync columns from source"**，確認所使用的 Dataset（`L5TaskPeriodic` 或靜態 SQL Dataset）的 SQL 包含 `ORDER BY snapshot_date DESC`。

### Q: 選取日期時出現 `Arrow error: Cannot convert string to type DateTime`？
*   **原因**：ClickHouse 24.3 與 ISO 時間格式不相容。
*   **解法**：確認 Cube 定義中使用的是 `type: string` 搭配 `YYYY-MM-DD` 格式（目前系統已全面修正）。

### Q: 明細表 (L5TaskDetails) 查詢速度很慢？
*   **原因**：`L5TaskDetails` 使用 `FINAL` 關鍵字確保去重，在大時間範圍查詢時速度較慢。
*   **解法**：縮小 `taskStartDate` 的篩選範圍（建議以月為單位），避免全表掃描。

---

**相關文件**:
- Cube.js 語義層說明 → `docs/04_serving/CubeJS_Semantic_Layer.md`
- 核心指標定義 → `docs/03_metrics/01_Metrics_and_Data_Definitions.md`
- 明細欄位對照 → `docs/03_metrics/UI_Detail_Fields_Mapping.md`

---

**文件負責人**: AIT / Data Engineering  
**最後審核日期**: 2026-04-30
