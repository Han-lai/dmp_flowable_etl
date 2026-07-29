# (DEPRECATED) L5 Cube Model 使用說明

> **最後更新**: 2026-04-30
> **狀態**: ⛔ 此文件已廢棄 (Deprecated)

## ⚠️ 重要遷移公告

隨著系統全面升級至 **V4.3 Bitmap Cohort** 架構，舊版的 `gold.rmv_l5_task_completion_v2` 以及對應的 V2 系列 Cube 模型（例如 `cube_l5_task_periodic_v2.js`）皆已廢棄。

目前最新的 4 個 Active 模型為：
1. **`cube_l5_task_periodic.js`**
2. **`cube_l5_task_periodic_pivot.js`**
3. **`cube_l5_task_details.js`**
4. **`cube_dim_mfg_filter.js`**

### 👉 最新文件位置

請不要再參考本文件內的欄位與邏輯說明。所有關於 Cube.js 的最新語義層定義、維度與度量（Measures）公式、以及預聚合（Pre-aggregations）策略，已經統一集中管理於以下主控文件：

- 🔗 **[CubeJS 語義層與模型說明](../../../docs/04_serving/CubeJS_Semantic_Layer.md)**
- 🔗 **[Superset 圖表與 Dashboard 操作指引](../../../docs/04_serving/Superset_Chart_Guide.md)**

---
*(註：本文件保留僅為防止歷史外部連結失效，請勿再擴充本文件內容。)*