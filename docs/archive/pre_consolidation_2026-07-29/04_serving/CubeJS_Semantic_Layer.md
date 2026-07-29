# Cube.js 語義層定位與模型應用說明

**文件編號**: 04-SRV-001  
**最後更新**: 2026-05-28  
**狀態**: 正式發布 (Released)  
**維護者**: AIT / Data Engineering

---

## 1. 架構定位 (Architecture Positioning)

Cube.js 在本專案中扮演**統一指標網關 (Unified Metrics Gateway)** 與**併發保護層**的角色。由於 ClickHouse Server 76 僅配置 6GB RAM，Cube.js 透過語義轉置與預聚合機制，確保高併發查詢下系統的穩定性。

### 1.1 數據流向
```
ClickHouse (Gold Layer)
   │  (物理化聚合表 / 實體化視圖)
   ▼
Cube.js (Semantic Layer)
   │  (SQL 翻譯 / 指標定義 / 快取快照)
   ▼
Serving Layer (FastAPI / Node.js / Superset)
```

### 1.2 核心職責
- **語義轉置**：將複雜的 ClickHouse `UNION ALL` 與 `ARRAY JOIN` 腳本封裝為簡潔的 REST/GraphQL API 調用。
- **指標一致性**：確保前端各報表 (Superset, API) 使用的「完成率」或「ACC」算法完全統一。
- **高併發防禦**：利用 Pre-aggregations 機制攔截並合併重複的查詢請求，大幅度減少對資料庫的存取壓力。

---

## 2. Cube 模型總覽 (Model Overview)

本專案目前共實作三個 Cube 模型，各司其職：

> **架構異動（2026-06-16 移除）**：`DimMfgFilter`（`cube_dim_mfg_filter.js`）已廢棄移除。Superset 篩選器的維度資料改由 `L5TaskPeriodic` 主模型提供，或採靜態 SQL Dataset。

| Cube 名稱 | 資料來源 | 主要用途 |
| :--- | :--- | :--- |
| **`L5TaskPeriodic`** | `gold.rmv_l5_task_summary` | KPI 聚合主模型，提供日/週/月三種粒度的完成率指標 |
| **`L5TaskPeriodicPivot`** | `gold.rmv_l5_task_summary` | Pivot 表格專用長表模型，適合 Superset Pivot Table |
| **`L5TaskDetails`** | `silver.mv_fact_task_vx FINAL` | 明細下鑽模型，提供工單層級的任務明細查詢 |

---

## 3. 數據建模定義 (Data Schema)

### 3.0 DimMfgFilter — 篩選選單模型（★ 已廢棄，移除於 2026-06-16）

> 原 `DimMfgFilter` 模型（`cube_dim_mfg_filter.js`）已從 Cube.js 語意層移除。
>
> **設計背景**：原先 Superset 篩選器直接查詢主模型時，選單載入超過 60 秒並觸發 Network Error。`DimMfgFilter` 透過 `DISTINCT` 只抓維度組合，將查詢壓縮至 < 0.1s。
>
> **移除原因**：維護成本高且查詢模式改變後效益降低。
>
> **現行替代方案**：Superset Native Filter 改為直接對 `L5TaskPeriodic` 的維度欄位（`diffRegion`、`diffPlant` 等）進行篩選，或採靜態 SQL Dataset。

---

模型基於 `gold.rmv_l5_task_completion` 定義，專門針對 L5 任務完成率場景優化。

### 2.1 核心度量 (Measures)

> **架構說明 (V4.3)**：`L5TaskPeriodic` 與 `L5TaskPeriodicPivot` 已改讀 ETL 預聚合整數表 `gold.rmv_l5_task_summary`，所有指標均以 `SUM(integer_column)` 計算，不再進行即時 Bitmap 運算。

| 度量名稱 | 核心 SQL / 指標邏輯 | 說明 |
| :--- | :--- | :--- |
| **Total Tasks** | `SUM(total_qty)` | 視窗內累計總任務數 (分母) |
| **Todo Qty** | `SUM(todo_qty)` | 未認領任務數 |
| **Doing Qty** | `SUM(doing_qty)` | 進行中任務數 |
| **Done Qty** | `SUM(done_qty)` | 已完結任務數 |
| **Acc Qty** | `SUM(acc_qty)` | **累積在途量**：7 日滾動在途唯一任務數 |
| **Acc Total Qty** | `SUM(acc_total_qty)` | **7日滾動總任務數**：用於日維度 Acc Rate 的分母 |
| **Done Rate** | `doneQty * 100.0 / nullIf(totalQty, 0)` | 結案率 |
| **Acc Rate** | (見說明) | **累積負載率/落後率**：<br>1. **日維度**: `accQty / accTotalQty` (7日滾動積壓率)<br>2. **週/月維度**: `(todoQty + doingQty) / totalQty` (週期落後率) |


### 2.2 核心維度 (Dimensions)

| 維度名稱 | 類型 | 說明 |
| :--- | :--- | :--- |
| **Period Name** | `string` | 時間粒度標籤 (例如：`Month`, `W44`, `2026-04-14`) |
| **Vx Type** | `string` | 簽核版本識別 (V1 / V2 / V3) |
| **Organization** | `string` | 製造五階維度 (Region, Plant, Factory, Line) |
| **Snapshot Date**| `time` | 篩選基準日，驅動模型內的 Anchor Date 邏輯 |

---

## 3. Schema 程式碼塊範例 (YAML/JS)

以下為 V4.3 架構下 `L5TaskPeriodic` Cube 的核心定義片段（讀取預聚合整數表）：

```javascript
cube(`L5TaskPeriodic`, {
  // V4.3: 直接讀取 ETL 預聚合整數表，不再即時計算 Bitmap
  sql: `
  WITH
      (SELECT max(snapshot_date) FROM gold.rmv_l5_task_summary FINAL WHERE period_type = 'Day'
         AND ${FILTER_PARAMS.L5TaskPeriodic.snapshotDate.filter("snapshot_date")} ...) AS anchor_dt
  SELECT * FROM (
      -- Month / Week / Day 三段 UNION ALL，各自篩選對應 period_type
      SELECT 'Month' as granularity, total_qty, todo_qty, doing_qty, done_qty, acc_qty, acc_total_qty, ...
      FROM gold.rmv_l5_task_summary FINAL WHERE period_type = 'Month' ...
      UNION ALL ...
  )`,

  measures: {
    // [數量指標]：直接 SUM 預聚合好的整數欄位
    totalQty: { type: `sum`, sql: `total_qty`, title: '總任務數' },
    todoQty:  { type: `sum`, sql: `todo_qty`,  title: '待辦數' },
    doingQty: { type: `sum`, sql: `doing_qty`, title: '進行中' },
    doneQty:  { type: `sum`, sql: `done_qty`,  title: '已完成' },
    accQty:   { type: `sum`, sql: `acc_qty`,   title: '累積在途(Acc)' },
    accTotalQty: { type: `sum`, sql: `acc_total_qty`, title: '7日滾動總量' },

    doneRate: {
      type: `number`,
      sql: `round(${doneQty} * 100.0 / nullIf(${totalQty}, 0), 2)`,
      title: '完成率%'
    },
    accRate: {
      type: `number`,
      // 日維度用 7 日滾動分母；週/月維度用週期總量
      sql: `CASE WHEN any(granularity) = 'Day'
                 THEN round(${accQty} * 100.0 / nullIf(${accTotalQty}, 0), 2)
                 ELSE round((${todoQty} + ${doingQty}) * 100.0 / nullIf(${totalQty}, 0), 2)
            END`,
      title: '積壓率%'
    }
  },

  dimensions: {
    periodName: { type: `string`, sql: `period_name`, title: '週期' },
    granularity: { type: `string`, sql: `granularity`, title: '粒度' },
    diffVxType:  { type: `string`, sql: `vx_type`,    title: 'Vx版本' },
    diffRegion:  { type: `string`, sql: `region`,     title: '區域' },
    diffPlant:   { type: `string`, sql: `plant`,      title: '廠區' },
    diffFactory: { type: `string`, sql: `factory`,    title: '工廠' },
    diffLine:    { type: `string`, sql: `line`,       title: '線體' },
    snapshotDate: { type: `string`, sql: `filter_date`, title: '快照日期篩選' }
  }
});
```

---

## 4. 預聚合應用 (Pre-aggregations)

針對 ClickHouse Server 76 的 6GB RAM 資源受限情境，Cube.js 採取以下預聚合策略：

### 4.1 核心策略：Rollup 資料切片
系統不啟用全量 OAP 同步，而是針對常用的報表視角建立 **Rollup**。

- **粒度定義**：預聚合至 `snapshot_date` + `vx_type` + `factory` 層級。
- **刷新頻率**：配合 ETL 管線 (例如：每日 05:00 完成計算)，將 `build_range` 設為同步後 1 小時後觸發。
- **快取有效期限**：設置 `refresh_key` 連結至下游 `gold.rmv_l5_task_completion` 的資料版本。

### 4.2 效能提升數據參考
- **無快取查詢**：約 1.2s ~ 1.5s (掃描 200MB+ 資料)。
- **預聚合命中**：**< 100ms** (掃描量趨近於 0)。

---

## 5. 調度機制：Time Machine 錨點邏輯

本專案實作了特殊的 **Anchor Date (錨點)** 邏輯：
1. **動態定位**：當使用者篩選日期範圍時，Cube.js 自動計算範圍內的最大日期作為 `anchor_dt`。
2. **多維展開**：依據此錨點，自動在 SQL 層面展開 Month、Week (W-n)、Day (D-n) 三種粒度，確保報表排版固定且邏輯連貫。

---

## 5. 明細下鑽 (Drill-through) 模型: L5TaskDetails

除了 KPI 流量表外，系統另外提供一個專用於明細查看的 Cube 模型 `L5TaskDetails`，支援從看板直接下鑽至單筆工單。

### 5.1 主要用途
- 在 Superset 圖表中點擊任意小計數字，直接跳轉至該廠線/工廠/線體在該時間區間內的任務明細清單。
- 無需返回原始資料庫，直接由 Cube.js 提供經語義轉換後的明細。

### 5.2 提供欄位

| 欄位名稱 | 內容說明 |
| :--- | :--- |
| `task_id` | 任務唯一識別碼 |
| `proc_inst_id` | 流程實例 ID |
| `task_name` | 節點名稱 |
| `vx_type` | 流程類型 (V1/V2/V3) |
| `region` / `plant` / `factory` / `line` | 製造五階維度 |
| `task_status` | 目前任務狀態 |
| `task_start_time` / `task_claim_time` / `task_end_time` | 任務三大時間節點 |
| `assignee_name` | 執行者姓名 |
| `mo_number` 等 11 欄 | 工單號碼、機種、棧板等業務擴充變數 |
| `is_excluded` / `exclude_reason` | 排除狀態與原因 |

---

**相關文件**:
- 系統架構總覽: `docs/01_architecture/Architecture_Overview.md`
- ETL 管線細節: `docs/03_metrics/02_ETL_Transformation_Pipeline.md`
- 核心指標定義: `docs/03_metrics/Metrics_and_Data_Definitions.md`

---

**文件負責人**: AIT / Data Engineering  
**審核狀態**: 已對照 `cube/model/cubes/cube_l5_task_periodic.js` 與 `cube_l5_task_details.js` 實作校對。  
**最後審核日期**: 2026-06-16（更新：`DimMfgFilter` 模型廢棄移除）
