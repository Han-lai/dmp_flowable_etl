# DMP Flowable 流程分析系統 (DMP Flowable Process Analytics)

本專案是一套基於 **Flowable BPM** 的自動化資料流與數據分析系統。其核心目標在於將分散的 BPM 流程簽核數據，透過 ETL Pipeline 整合至高效能的 ClickHouse 物理化數據倉儲，產出量化的生產管理指標（如：L5 任務完成率、累積在途量），為製造業產線管理層提供即時的數據決策支援。

---

## 1. 系統架構亮點 (Architecture Highlights)

本系統採用現代化數據倉儲架構，並因應 Server 76 環境資源限制，實作了具有高度彈性與極限效能的特徵：

*   **獎牌管線架構 (Medallion Architecture)**
    *   **Bronze 層**: 採用 Native ODBC Driver 18 結合 Adaptive Batching 進行高速抽取，繞過 JDBC 驅動死鎖問題。
    *   **Silver 層**: 執行 EAV 架構轉置 (Pivot) 與五階製造維度對齊，並實作 10 日滑動視窗避免 OOM。
    *   **Gold 層**: 導入 **「V4.3 Bitmap Cohort 物理化架構」**，全面捨棄耗能的 `ARRAY JOIN`，透過 `groupBitmapStateIf` 將 Todo/Doing/Done 同日結算與 7 日滾動 ACC 運算完全卸載至後台 ETL 批次處理。
*   **伺服器護城河 (Cube.js Semantic Gateway)**
    *   為解決高併發 OOM 瓶頸，全面禁止前端直連資料庫。透過 Cube.js 語意層進行 SQL 翻譯與結果快取攔截，將資料庫負載降低逾 98%。

---

## 2. 核心文件指引 (Documentation Index)

所有系統設計細節均已完整收錄於 `docs/` 文件庫中。欲深入了解特定主題，請參閱：

*   **📚 架構與部署**
    *   [Architecture_Overview.md](docs/01_architecture/Architecture_Overview.md) - 系統架構總覽、獎牌管線設計
    *   [ClickHouse_ODBC_Setup.md](docs/01_architecture/ClickHouse_ODBC_Setup.md) - Native ODBC 與資料同步規格
    *   [Deployment_Guide.md](docs/02_deployment/Deployment_Guide.md) - 環境配置、容器啟動與 ETL 維護手冊
*   **⚙️ 業務指標與管線**
    *   [ETL_Transformation_Pipeline.md](docs/03_metrics/ETL_Transformation_Pipeline.md) - 6 階轉換管線、視窗機制與 SQL 邏輯
    *   [Metrics_and_Data_Definitions.md](docs/03_metrics/Metrics_and_Data_Definitions.md) - 核心業務指標 (L5/L7) 語意與規則定義
*   **📊 展示與語意層**
    *   [CubeJS_Semantic_Layer.md](docs/04_serving/CubeJS_Semantic_Layer.md) - Cube.js 語意層定義與調度設定
    *   [API_Documentation.md](docs/04_serving/API_Documentation.md) - FastAPI L5 Insight 介面規格
    *   [Superset_Chart_Guide.md](docs/04_serving/Superset_Chart_Guide.md) - Superset 視覺化使用與設定指南
*   **🚀 效能與監控**
    *   [Physical_Gold_Benchmark_Report.md](docs/05_monitoring/Physical_Gold_Benchmark_Report.md) - 高併發極限壓測報告
    *   [ClickHouse_Benchmark_Guide.md](docs/05_monitoring/ClickHouse_Benchmark_Guide.md) - 效能負載測試 SOP

> **TIP:** 如果您是首次接觸此專案，建議從 **[Architecture_Overview.md](docs/01_architecture/Architecture_Overview.md)** 開始閱讀。

---

## 3. 快速上手 (Quick Start)

完整的 ETL 維護操作請參閱 `docs/02_deployment/Deployment_Guide.md`。以下為日常維運指令摘要：

### 1. 基礎架構更新 (Phase 0)
於首次部署或表結構 (Schema) 變更時執行，自動初始化所有 ClickHouse 實體表：
```powershell
python scripts/etl/setup_schema.py
```

### 2. 資料抽取同步 (Phase 1)
採用原生 ODBC 將 MSSQL 資料拉取至 Bronze 層 (支援 Watermark 自動斷點續傳)：
```powershell
python scripts/etl/sync_unified_odbc.py --table all
```

### 3. Silver & Gold 分析運算 (Phase 2)
驅動 Silver 事實表轉換與 Gold 加速表之分離聚合 (支援 Memory Limit Auto-Split 與 Checkpoint 機制)：
```powershell
# 執行每日排程更新 (自動回溯近期異動)
python scripts/etl/execute_etl.py --daily --low-ram

# 執行特定範圍之歷史補分
python scripts/etl/execute_etl.py --backfill --start 2025-01-01 --step-days 10 --low-ram
```

---

## 4. 效能優化里程碑 (Performance Results)

透過改用 **Native ODBC** 取代 JDBC Bridge、並全面套用 **Physical Gold 物理化架構**，系統達成了以下關鍵成就：

1. **極速抽取**：5,300 萬筆來源資料可於 **9.7 分鐘**內完成搬運，平均吞吐量 9 萬筆/秒。
2. **端到端高效**：自 MSSQL 抽取、Silver 清洗、至 Gold 實體化指標產出 (2,500 萬筆次運算)，全程僅需 **~10.1 分鐘**，且全程限制 RAM 於 5.5 GiB 內安全執行。
3. **百人併發零故障**：經 `clickhouse-benchmark` 實測，在面對 100 個獨立的 Dashboard 複雜查詢並發衝擊下，P99 延遲僅 **0.39 秒**，不僅達成 100% 成功率，更較未優化前快上 **11 倍** 以上。

---

## 5. 專案結構 (Project Structure)

```text
dmp_flowable/
├── api/                        # FastAPI 端點實作 (Serving Layer)
│   ├── main.py                 # API 伺服器入口
│   └── routers/                # 業務指標 API 路由對接
├── cube/                       # Cube.js 語意層 (Semantic Gateway)
│   ├── conf/                   # 資料庫連線配置與環境變數
│   ├── model/                  # Metrics/Dimensions 幾何定義檔 (.js)
│   └── cube.js                 # 核心攔截器與列級權限配置 (Security Context)
├── docs/                       # 核心技術手冊與架構文件 (Single Source of Truth)
├── infra/                      # 基礎設施部署配置 (Docker/CI/CD)
│   └── clickhouse/             # ClickHouse 伺服器配置 (如記憶體與併發控流)
├── scripts/                    # Python 調度腳本與工具 (Transport Layer)
│   ├── etl/
│   │   ├── setup_schema.py      # DDL 結構自動部署腳本
│   │   ├── sync_unified_odbc.py # Bronze 層 Native ODBC 高速同步引擎
│   │   └── execute_etl.py       # Silver/Gold 層運算與 Watermark 調度主程式
│   └── security_scan_results/  # 最新資安掃描報告 (Fortify / Black Duck)
└── sql/                        # 運算邏輯中心 (Transformation Layer)
    ├── etl/
    │   ├── schema/             # 各層實體表與視圖 DDL 定義 (Schema 01~07)
    │   └── dml/                # 各階段資料轉換 SQL (如 Pivot, Milestone, ACC)
    └── queries/                # 日常維護與查帳用探索語法
```
