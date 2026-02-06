# L5 專案完成度與 Superset 定義總表

## 1. L5 專案完成度概覽 (Project Completion Status)

截至 2026-02-06，L5 任務指標專案的核心架構與關鍵指標已完成開發與驗證。

| 項目 (Component) | 狀態 | 說明 (Details) |
| :--- | :--- | :--- |
| **ETL 數據流** | ✅ 完成 | 完整覆蓋 Bronze -> Silver -> Gold 層，包含 Refreshable MView 架構。 |
| **數據對齊 (Validation)** | ✅ 完成 | 12/25 基準日數據達成三方對齊 (Raw=192, Gold=192)。ACC (在途量) 誤差收斂至 1 筆。 |
| **Cube.js 架構** | ✅ 完成 | 採用雙模型策略：`L5TaskCompletion` (Table) 與 `L5TaskPeriodic` (Chart)。 |
| **Superset 支援** | ✅ 完成 | 支援 Pivot Table, Mixed Chart (Dual Axis), Tooltip 顯示。 |
| **自動化刷新** | ✅ 完成 | Gold 層 MView 已配置後台自動刷新機制。 |
| **人員利用率 (L7)** | ⏳ 待啟動 | 下階段重點開發項目。 |

---

## 2. Superset 圖表定義指南 (Chart Definitions)

以下是針對使用者最常使用的兩類圖表的標準設定參數。

### A. L5 任務週期混合圖 (Periodic Mixed Chart)

**用途**: 檢視特定時間點 (預設最新) 的 月/週/日 趨勢，並同時監控數量與完成率。

| 設定項 (Setting) | 值 (Value) | 備註 |
| :--- | :--- | :--- |
| **Dataset** | `L5 Task Periodic` | Cube: `cube_l5_task_periodic.js` |
| **Chart Type** | **Mixed Timeseries Chart** | |
| **X-Axis** | `periodName` | 顯示文字 (Dec., W1, 12-31...) |
| **Shared Sort By** | `periodSortOrder` | **Ascending** (升冪) |
| **Query A (Bar)** | **Metrics**: `totalQty` | **不可**設定 Dimension/Group By |
| **Query B (Line)** | **Metrics**: `doneRate` | 勾選 **Secondary Y Axis** (副軸) |
| **Time Filter** | *(Optional)* | 目前版本預設顯示最新日期，篩選功能暫時鎖定。 |

### B. L5 任務完成率明細表 (Completion Pivot Table)

**用途**: 每日/每週運營檢討，查看各地區、廠區的詳細數據。

| 設定項 (Setting) | 值 (Value) | 備註 |
| :--- | :--- | :--- |
| **Dataset** | `L5 Task Completion` | Cube: `cube_l5_task_completion.js` |
| **Chart Type** | **Pivot Table v2** | |
| **Rows** | `region`, `plant`, `line` | 依需求拖拉組織層級 |
| **Columns** | `vxType` (V1/V3) | |
| **Metrics** | `doneCount`, `totalTask`, `accTodoDoing` | |
| **Time Range** | Last Day / Last Week | 支援完整時間篩選 |
