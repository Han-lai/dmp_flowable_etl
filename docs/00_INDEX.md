# DMP Flowable 專案文件索引 (Documentation Index)

本專案文件庫已系統化重整，旨在提供從「架構」到「指標」再到「展示層」的完整技術指引。

---

## 1. 系統架構與部署運維 (Architecture & Deployment)
- [Architecture_Overview.md](01_architecture/Architecture_Overview.md): **核心文件**。系統架構總覽、獎牌架構 (Medallion) 及技術堆疊剖析。
- [ClickHouse_ODBC_Setup.md](01_architecture/ClickHouse_ODBC_Setup.md): 數據同步規格。MSSQL → ClickHouse 之 Native ODBC 配置與同步工具指令。
- [Deployment_Guide.md](02_deployment/Deployment_Guide.md): 部署與維運手冊。包含 Docker 啟動、ETL 同步引擎 (`sync_unified_odbc.py`) 與 Watermark 增量機制之操作細節。

## 2. 資料管線與指標定義 (Pipeline & Metrics)
- [ETL_Transformation_Pipeline.md](03_metrics/ETL_Transformation_Pipeline.md): **核心邏輯**。從 Bronze → Silver → Gold 之 7 階段轉換管線 SQL 邏輯（含 Stage 7 預聚合彙總表）、視窗機制與維護 SOP。
- [Metrics_and_Data_Definitions.md](03_metrics/Metrics_and_Data_Definitions.md): 業務指標語義。六項核心指標定義、演進歷程、五階維度血緣與查帳基準。
- [Developer_Guide_New_Metrics.md](03_metrics/04_Developer_Guide_New_Metrics.md): **核心開發手冊**。指導如何新增指標，包含 DDL/DML 撰寫規範、Pipeline 配置與自動化測試流程。

## 3. 展示層與語義層 (Serving & Semantic Layer)
- [CubeJS_Semantic_Layer.md](04_serving/CubeJS_Semantic_Layer.md): **核心閘道**。Cube.js 語義層定位、Dimensions/Measures 定義、預聚合策略與調度機制。
- [API_Documentation.md](04_serving/API_Documentation.md): FastAPI L5 Insight API 介面規格與調用範例。
- [Superset_Chart_Guide.md](04_serving/Superset_Chart_Guide.md): 視覺化整合。Cube.js 語義層與 Superset 整合指南。

## 4. 效能與監控系統 (Monitoring & Benchmarks)
- [Physical_Gold_Benchmark_Report.md](05_monitoring/Physical_Gold_Benchmark_Report.md): 效能壓測分析。物理化架構 vs. 即時聚合之效能對比摘要。
- [ClickHouse_Benchmark_Guide.md](05_monitoring/ClickHouse_Benchmark_Guide.md): 壓測操作手冊。透過 `clickhouse-benchmark` 進行極限負載測試的標準流程。
- [Grafana_Dashboard_Setup.md](05_monitoring/Grafana_Dashboard_Setup.md): 維運監控。Grafana 面板配置與系統健康指標說明。

---
*最後重整日期: 2026-05-28*  
*維護單位: AIT / Data Engineering*
