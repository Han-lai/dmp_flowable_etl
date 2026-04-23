# DMP Flowable 文件庫索引 (Documentation Index)

> **最後更新**: 2026-04-23  
> **文件總數**: 16 份（含 1 份歸檔）

---

## 📚 01_architecture — 架構設計

| 文件 | 說明 |
| :--- | :--- |
| [Architecture_Overview.md](01_architecture/Architecture_Overview.md) | 系統架構總覽、Medallion 分層設計、ETL 工具鏈與硬體環境 |
| [ClickHouse_ODBC_Setup.md](01_architecture/ClickHouse_ODBC_Setup.md) | Native ODBC Driver 18 設定、DSN 配置與資料同步規格 |
| [ODBC_vs_JDBC_vs_Airbyte.md](01_architecture/ODBC_vs_JDBC_vs_Airbyte.md) | 三種 MSSQL → ClickHouse 匯入方案效能與成本比較 |

---

## 🚀 02_deployment — 部署與維運

| 文件 | 說明 |
| :--- | :--- |
| [Deployment_Guide.md](02_deployment/Deployment_Guide.md) | 環境配置、ETL 維護手冊、Watermark 管理、**全新環境部署 SOP (§6)** |

---

## ⚙️ 03_metrics — 指標定義與 ETL 管線

| 文件 | 說明 |
| :--- | :--- |
| [ETL_Transformation_Pipeline.md](03_metrics/ETL_Transformation_Pipeline.md) | 6 階 ETL 轉換管線、視窗機制、SQL 邏輯（**SQL 唯一維護來源**） |
| [Metrics_and_Data_Definitions.md](03_metrics/Metrics_and_Data_Definitions.md) | 核心業務指標語義定義（L5/L7）、狀態分類規則 |
| [04_Developer_Guide_New_Metrics.md](03_metrics/04_Developer_Guide_New_Metrics.md) | 新增 KPI 開發者操作指南（6 步 SOP） |
| [Detailed_Audit_Guide.md](03_metrics/Detailed_Audit_Guide.md) | 數據對帳操作手冊、Gold vs UI 結果（11月+12月）、差異優先級追蹤 |

---

## 📊 04_serving — 展示與語義層

| 文件 | 說明 |
| :--- | :--- |
| [CubeJS_Semantic_Layer.md](04_serving/CubeJS_Semantic_Layer.md) | Cube.js 語義層定位、模型定義與預聚合策略 |
| [API_Documentation.md](04_serving/API_Documentation.md) | FastAPI L5 Insight API 端點規格與範例 |
| [Superset_Chart_Guide.md](04_serving/Superset_Chart_Guide.md) | Superset 圖表設定指南（V2 Time Machine、Pivot Table） |

---

## 🔍 05_monitoring — 效能監控

| 文件 | 說明 |
| :--- | :--- |
| [Physical_Gold_Benchmark_Report.md](05_monitoring/Physical_Gold_Benchmark_Report.md) | 實體化金層架構效能與驗收報告（併發壓測） |
| [ClickHouse_Benchmark_Guide.md](05_monitoring/ClickHouse_Benchmark_Guide.md) | clickhouse-benchmark 壓測操作手冊 |
| [Grafana_Dashboard_Setup.md](05_monitoring/Grafana_Dashboard_Setup.md) | Grafana 儀表板設定指南（PromQL + ClickHouse SQL） |
| [End_to_End_Execution_Report.md](05_monitoring/End_to_End_Execution_Report.md) | 端到端執行報告（bronze/bronze_opt 效能對比） |

---

## 🎤 presentation — 簡報與對外文件

| 文件 | 說明 |
| :--- | :--- |
| [DMP_Flowable_Technical_Documentation.md](presentation/DMP_Flowable_Technical_Documentation.md) | 技術設計規格書 v5.0（對外簡報用整合版） |
| [presentation_script_15min.md](presentation/presentation_script_15min.md) | 15 分鐘技術簡報講稿 |

---

## 📦 archive — 歸檔文件

| 文件 | 說明 |
| :--- | :--- |
| [Done指標差異問題.md](archive/Done指標差異問題.md) | ~~已整併至 `Detailed_Audit_Guide.md`~~（2026-04-23 歸檔） |
