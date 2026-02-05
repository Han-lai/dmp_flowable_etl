# L5 任務狀態對比報表需求說明書 (L5 Status Comparison Report Requirements)

> **類型**: 技術規範 / 報表定義  
> **最後更新**: 2026-02-04  
> **狀態**: 已驗證

## 🎯 1. 報表目標 (Objective)
產出 L5 任務的多維度對比報表，整合 Snapshot (時點快照) 與 Accumulated (區間累計) 指標，用於監控不同時間顆粒度（日/週/月）下的任務處理狀況與積壓趨勢。

## 📊 2. 報表格式與定義 (Format & Definitions)

### 2.1 維度欄位 (Left Dimensions)
依序排列：
1.  **流程區域 (Vx Type)**: 例如 V1, V2, V3.
2.  **地區 (Region)**: 標準為 `CNE`, `WJ` 等。需注意對應 MDM 的 `MFG_SITE` 欄位。
3.  **製造廠區 (Plant)**: 例如 `WJ2`, `DG3`.
4.  **製造產品類 (Factory)**: 例如 `NBU`, `NPE`, `NBA`.
5.  **線別 (Line)**: 例如 `E5`, `N01`.
6.  **任務狀態 (Task Status)**: 指標名稱。

### 2.2 指標清單 (Metrics - In Order)
| 順序 | 指標名稱 | 業務定義與計算邏輯 |
| :--- | :--- | :--- |
| 1 | **Total Task** | 總任務量。計算方式：SUM(Daily Snapshot Total)。 |
| 2 | **Todo** | 待辦任務量。計算方式：SUM(Daily Snapshot Todo)。 |
| 3 | **Doing** | 處理中任務量。計算方式：SUM(Daily Snapshot Doing)。 |
| 4 | **Done** | 已完成任務量。計算方式：SUM(Daily Snapshot Done)。 |
| 5 | **Doing+Done** | 執行中與完成加總。計算方式：`Doing Qty` + `Done Qty`。 |
| 6 | **Todo+Doing(Acc)**| **累計在途任務數 (ACC)**。計算方式：指定區間內曾經處於待辦或處理中狀態的唯一任務 ID 去重數 (Internal Unique Count)。 |

### 2.3 時間顆粒度 (Time Columns)
由左至右排列：
- **Monthly**: 指定月份 (例如 Dec)。
- **Weekly**: 指定週次 (例如 W50, W51, W52)，週次起始為週一 (Mon) 至週日 (Sun)。(指定日期地當次周次及往前推3周)
- **Daily**: 指定連續日期範圍 (例如 2025-12-25 至 2025-12-31)，**由舊到新**。

每个時間單位需同時輸出：
- **Task Qty**: 數量。
- **(%)**: `Task Qty` / `Total Task` (同週期百分比)。

## ⚙️ 3. 技術實現規則 (Technical Rules)
- **資料來源**:
    - Snapshot 類: `gold.rmv_l5_task_completion`
    - ACC 類: `silver.mv_fact_task_vx`
- **Region 歸屬機制**: 
    - 必須取自 MDM 的 `region_code` (對應 `common_mdm_factory_area_master` 的 `MFG_SITE` 欄位)。
- **空值處理**: 某時間區間無資料請顯示 `0`，但欄位仍需保留以維持表格結構。

## 📝 4. 原始需求 Prompt 參考
> 我需要你協助計算報表下半部的表格資料，不需要產出圖表。
> 請完全依照現有報表的欄位定義、欄位順序與計算邏輯輸出結果，不可自行調整格式。表格左側維度欄位依序為：流程區域(Vx)、地區、製造廠區、製造產品類、線別、任務狀態(Task Status)。Task Status 僅包含：Total Task、Todo、Doing、Done、Doing+Done、Todo+Doing(Acc)，且順序不可變。右側時間欄位請依序輸出：Dec、W49、W50、W51，以及 Daily（2025-12-25 至 2025-12-31，由舊到新）。每個時間單位需同時輸出 Task Qty 與 (%)。百分比定義為該狀態 Task Qty 除以同一時間區間內的 Total Task。Weekly、Monthly 與 Daily 使用相同的加總邏輯。某時間區間無資料請顯示 0，但欄位仍需保留。

---
## 🛠️ 5. 自動化腳本位置
`scripts/validation/generate_l5_full_report.py`
