# Cube.js 語意層

> **最後更新**: 2026-04-30
> **資料來源**: `gold.rmv_l5_task_completion` (V4.3 Bitmap Cohort版)

## 架構

```
ClickHouse (Gold Layer)
        │
        ▼
    Cube.js
    ├── REST API (port 4000)
    ├── Playground (port 4000)
    └── Model (4 個 Active Cube)
        │
        ▼
    Superset Dashboard
```

## 目錄結構 (Logical Structure)

```text
cube/
├── README.md                    # 本檔案
└── model/                       # Cube.js 語義模型定義
    ├── cubes/                   # 資料立方體定義
    │   ├── cube_l5_task_periodic.js    # ✅ L5 週期報表 (Active)
    │   ├── cube_l5_task_details.js     # ✅ L5 任務明細下鑽 (Active)
    │   └── cube_dim_mfg_filter.js      # ✅ 維度選單模型 (Active)
    └── views/                   # 預定義視圖
```

> [!NOTE]
> **部署檔案 (Infrastructure)** 與**詳細的模型欄位規格**，已統一移至以下文件集中管理：
> - 模型語義與聚合邏輯：`docs/04_serving/CubeJS_Semantic_Layer.md`
> - 部署與設定指引：`docs/04_serving/Superset_Chart_Guide.md`

## Active Models

本專案目前使用 4 個核心模型，詳細的維度與度量定義（包含 `bitmapCardinality` 計算邏輯）請詳見 [CubeJS_Semantic_Layer.md](../../docs/04_serving/CubeJS_Semantic_Layer.md)。

1. **`L5TaskPeriodic`**: 處理日/週/月三種粒度的 Bitmap 完成率。
2. **`L5TaskPeriodicPivot`**: 處理 Superset Pivot Table 報表。
3. **`L5TaskDetails`**: 處理前端明細下鑽，包含 11 個業務變數與 Assignee。
4. **`DimMfgFilter`**: 專門用於加速 Superset 篩選選單。

## 環境設定參考

| 變數 | 預期設定 | 說明 |
|------|--------|------|
| `CUBEJS_DB_TYPE` | `clickhouse` | 資料庫類型 |
| `CUBEJS_DB_HOST` | `REDACTED_IP` | ClickHouse 主機 |
| `CUBEJS_DB_PORT` | `8123` | ClickHouse HTTP Port |
| `CUBEJS_DB_USER` | `default` | 使用者 |
| `CUBEJS_DB_NAME` | `default` | 預設 DB |
