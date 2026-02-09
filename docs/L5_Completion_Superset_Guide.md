# L5 專案完成度與 Superset 定義總表

## 1. L5 專案完成度概覽 (Project Completion Status)

截至 2026-02-09，L5 任務指標專案的核心架構與關鍵指標已完成開發與驗證。

| 項目 (Component) | 狀態 | 說明 (Details) |
| :--- | :--- | :--- |
| **ETL 數據流** | ✅ 完成 | 完整覆蓋 Bronze -> Silver -> Gold 層，包含 Refreshable MView 架構。 |
| **數據對齊 (Validation)** | ✅ 完成 | 12/25 基準日數據達成三方對齊 (Raw=192, Gold=192)。ACC (在途量) 誤差收斂至 1 筆。 |
| **Cube.js 架構** | ✅ 完成 | 提供 V1 (JS Logic) 與 V2 (SQL Logic) 雙模型，V2 支援時光機功能。 |
| **Superset 支援** | ✅ 完成 | 支援 Pivot Table, Mixed Chart (Dual Axis), Tooltip 顯示。 |
| **自動化刷新** | ✅ 完成 | Gold 層 MView 已配置後台自動刷新機制。 |
| **人員利用率 (L7)** | ⏳ 待啟動 | 下階段重點開發項目。 |

---

## 2. Superset 圖表定義指南 (Chart Definitions)

以下是針對使用者最常使用的圖表設定參數。

### A. L5 任務週期混合圖 (V1 Standard)

**用途**: 檢視特定時間點 (預設最新) 的 月/週/日 趨勢。

| 設定項 (Setting) | 值 (Value) | 備註 |
| :--- | :--- | :--- |
| **Dataset** | `L5 Task Periodic` | Cube: `cube_l5_task_periodic.js` |
| **Chart Type** | **Mixed Timeseries Chart** | |
| **X-Axis** | `periodName` | 顯示文字 (Dec., W1, 12-31...) |
| **Shared Sort By** | `periodSortOrder` | **Ascending** (升冪) |
| **Query A (Bar)** | **Metrics**: `totalQty` | **不可**設定 Dimension/Group By |
| **Query B (Line)** | **Metrics**: `doneRate` | 勾選 **Secondary Y Axis** (副軸) |

### B. L5 任務週期報表 V2 (Time Machine & 8 Days)

**用途**: 進階報表。支援「指定任意日期」回溯查看，並完整顯示當日 + 前 7 天 (共 8 天) 的日趨勢。

| 設定項 (Setting) | 值 (Value) | 備註 |
| :--- | :--- | :--- |
| **Dataset** | `L5 Task Periodic V2` | Cube: `cube_l5_task_periodic_v2.js` |
| **Chart Type** | **Mixed Timeseries Chart** | |
| **X-Axis** | `periodName` | ⚠️ **注意**: 請勿使用 snapshotDate 當 X 軸 |
| **Shared Sort By** | `periodSortOrder` | **Ascending** (升冪) |
| **Query A (Bar)** | **Metrics**: `totalQty` | |
| **Query B (Line)** | **Metrics**: `doneRate` | 勾選 **Secondary Y Axis** (副軸) |
| **關鍵動作: Time Range** | 設定 **TIME** 區塊: | 已全面支持 YYYY-MM-DD 或長字串 |
| - Time Column | `snapshotDate` | |
| - Time Range | **Custom** (自定義) | |
| - Start / End | `2025-12-31` | **起始與結束選同一天** 或使用 Dashboard 分別選 Start/End |

> [!TIP]
> **V2 篩選穩定化**：現在系統已具備 Triple-OR 魯棒性，能自動處理 Superset 帶入的 `.000000` 微秒字串，用戶不再需要擔心「Cannot convert string to Date」錯誤。

---

## 3. Dashboard 設定指南 (Dashboard Setup)

在 Dashboard 層級，請使用 **Native Filters** (左側過濾器欄) 來統一控制圖表。

### 設定「時光機」日期篩選器
1.  **進入編輯模式**: 点击 Dashboard 右上角的 `Edit Dashboard` (筆形圖示)。
2.  **新增過濾器**: 在左側 `Filters` tab 點擊 `+ Add/Edit Filters`。
3.  **配置參數**:
    *   **Filter Type**: `Time Range` (時間範圍)。
    *   **Name**: 命名為 `Anchor Date` 或 `基準日`。
    *   **Scoping**: 勾選包含 V2 圖表的 Tab。
4.  **使用方式 (User Guide)**:
    *   使用者點選 `Anchor Date` 濾鏡。
    *   選擇 **Custom** -> **Specific Date** (若版本支援) 或 **Start/End 選同一天**。
    *   點擊 **Apply**，V2 圖表即會顯示該基準日往前推 8 天的完整趨勢。

### C. L5 任務完成率明細表 (Completion Pivot Table)

**用途**: 每日/每週運營檢討，查看各地區、廠區的詳細數據。

| 設定項 (Setting) | 值 (Value) | 備註 |
| :--- | :--- | :--- |
| **Dataset** | `L5 Task Completion` | Cube: `cube_l5_task_completion.js` |
| **Chart Type** | **Pivot Table v2** | |
| **Rows** | `region`, `plant`, `line` | 依需求拖拉組織層級 |
| **Columns** | `vxType` (V1/V3) | |
| **Metrics** | `doneCount`, `totalTask`, `accTodoDoing` | |
| **Time Range** | Last Day / Last Week | 支援完整時間篩選 |
