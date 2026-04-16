# Cube.js 語義層定位與模型應用說明

**文件編號**: 04-SRV-001  
**版本**: 1.0  
**最後更新**: 2026-04-14  
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

## 2. 數據建模定義 (Data Schema)

模型基於 `gold.rmv_l5_task_completion` 定義，專門針對 L5 任務完成率場景優化。

### 2.1 核心度量 (Measures)

| 度量名稱 | 核心 SQL / 指標邏輯 | 說明 |
| :--- | :--- | :--- |
| **Total Tasks** | `sum(total_task)` | 視窗內累計總任務數 (分母) |
| **Todo Qty** | `sum(todo_count)` | 未認領任務數 |
| **Doing Qty** | `sum(doing_count)` | 進行中任務數 |
| **Done Qty** | `sum(done_count)` | 已完結任務數 |
| **Acc Qty** | `sum(acc_todo_doing)` | **累積在途量**：7 日滾動在途唯一任務數 |
| **Done Rate** | `done_qty / total_qty` | 結案率 |
| **Acc Rate** | `acc_qty / acc_total_qty` | **累積負載率** (以 7 日滑動總量為分母) |

### 2.2 核心維度 (Dimensions)

| 維度名稱 | 類型 | 說明 |
| :--- | :--- | :--- |
| **Period Name** | `string` | 時間粒度標籤 (例如：`Month`, `W44`, `2026-04-14`) |
| **Vx Type** | `string` | 簽核版本識別 (V1 / V2 / V3) |
| **Organization** | `string` | 製造五階維度 (Region, Plant, Factory, Line) |
| **Snapshot Date**| `time` | 篩選基準日，驅動模型內的 Anchor Date 邏輯 |

---

## 3. Schema 程式碼塊範例 (YAML/JS)

以下為符合現有 Gold Layer 欄位結構的 Cube.js JavaScript 定義片段：

```javascript
cube(`L5TaskPeriodic`, {
  sql: `SELECT * FROM gold.rmv_l5_task_completion`,

  measures: {
    totalQty: { type: `sum`, sql: `total_task`, title: '總任務數' },
    todoQty: { type: `sum`, sql: `todo_count`, title: '待辦數' },
    doingQty: { type: `sum`, sql: `doing_count`, title: '進行中' },
    doneQty: { type: `sum`, sql: `done_count`, title: '已完成' },
    
    // 累積在途量 (ACC) 核心度量
    accQty: { type: `sum`, sql: `acc_todo_doing`, title: '累積在途(Acc)' },
    
    // 比率計算範例
    doneRate: {
      type: `number`,
      sql: `round(sum(done_qty) * 100.0 / nullIf(sum(total_qty), 0), 2)`,
      title: '完成率%'
    }
  },

  dimensions: {
    periodName: { type: `string`, sql: `period_name`, title: '週期' },
    
    // 製造五階組織維度
    vxType: { type: `string`, sql: `vx_type`, title: 'Vx版本' },
    region: { type: `string`, sql: `region`, title: '區域' },
    plant: { type: `string`, sql: `plant`, title: '廠區' },
    factory: { type: `string`, sql: `factory`, title: '工廠' },
    line: { type: `string`, sql: `line`, title: '線體' },
    
    snapshotDate: {
      type: `time`,
      sql: `snapshot_date`,
      title: '快照日期'
    }
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

**相關文件**:
- 系統架構總覽: `docs/01_architecture/Architecture_Overview.md`
- ETL 管線細節: `docs/03_metrics/ETL_Transformation_Pipeline.md`
- 核心指標定義: `docs/03_metrics/Metrics_and_Data_Definitions.md`

---

**文件負責人**: AIT / Data Engineering  
**審核狀態**: 已對照 `cube/model/cubes/cube_l5_task_periodic.js` 實作校對。
