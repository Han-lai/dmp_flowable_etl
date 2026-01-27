# 資料管道專案結構分析報告

## 專案概述
**資料流**: MSSQL → JDBC Bridge → ClickHouse → CubeJS → Superset
**專案類型**: ETL 資料管道 + 商業智慧儀表板

## 第一步：現有檔案分析

### 🔧 執行腳本 (Scripts)
| 檔案 | 用途 | 類型 |
|------|------|------|
| `scripts/verify_mssql_clickhouse_reconciliation.py` | MSSQL與ClickHouse資料對帳驗證 | 驗證腳本 |
| `scripts/verify_mview_pipeline_completion.py` | MVIEW管道完整性驗證 | 驗證腳本 |
| `scripts/execute_end_to_end_pipeline.py` | 端到端管道執行 | 執行腳本 |
| `scripts/execute_silver_dimension_update.py` | Silver層維度更新 | 資料處理腳本 |
| `scripts/execute_gold_dimension_update.py` | Gold層維度更新 | 資料處理腳本 |
| `scripts/backup_and_update_silver_mview.py` | Silver MVIEW備份更新 | 維護腳本 |
| `scripts/production_environment_test.py` | 生產環境測試 | 測試腳本 |
| `scripts/debug_superset_cne_wj2_nbu_e5_2025_12_25.py` | Superset問題診斷 | 除錯腳本 |
| `check_existing_tables.py` | 檢查資料表存在性 | 工具腳本 |
| `test_clickhouse_connection.py` | ClickHouse連線測試 | 工具腳本 |

### 🗃️ SQL 檔案
| 檔案 | 用途 | 類型 |
|------|------|------|
| `clickhouse/ddl/00_databases.sql` | 建立資料庫結構 | DDL |
| `clickhouse/ddl/10_bronze_sources.sql` | Bronze層資料表 | DDL |
| `clickhouse/ddl/20_silver_views_and_mviews.sql` | Silver層Views和MVIEWs | DDL |
| `clickhouse/ddl/30_gold_views_and_mviews.sql` | Gold層Views和MVIEWs | DDL |
| `clickhouse/ddl/40_validation_queries.sql` | 驗證查詢 | DDL |
| `sql/create_silver_dim_mfg_five_level.sql` | 製造五階維度表 | 業務邏輯 |
| `sql/update_silver_dimension_backfill_logic.sql` | Silver維度補齊邏輯 | 業務邏輯 |
| `sql/validate_varinst_mdm_mapping.sql` | VARINST MDM對應驗證 | 驗證查詢 |

### 🎯 CubeJS 資料模型
| 檔案 | 用途 | 類型 |
|------|------|------|
| `cube/model/cubes/cube_l5_dashboard_summary.js` | L5儀表板彙總模型 | 資料模型 |
| `cube/model/cubes/cube_gold_l5_task_completion.js` | L5任務完成度模型 | 資料模型 |
| `cube/.env.example` | CubeJS環境變數範例 | 設定檔 |
| `cube/docker-compose.yml` | CubeJS Docker設定 | 設定檔 |

### 📋 設定檔
| 檔案 | 用途 | 類型 |
|------|------|------|
| `package.json` | Node.js專案設定 | 設定檔 |
| `docker/docker-compose.yml` | Docker服務編排 | 設定檔 |
| `docker/clickhouse/` | ClickHouse Docker設定 | 設定檔 |

### 📚 文件
| 檔案 | 用途 | 類型 |
|------|------|------|
| `README.md` | 專案說明 | 文件 |
| `REBUILD_GUIDE.md` | 重建指南 | 文件 |
| `docs/data_pipeline_diagram.md` | 資料管道架構圖 | 架構文件 |
| `docs/metric_definitions.md` | 指標定義 | 業務文件 |
| `docs/superset_usage_guide.md` | Superset使用指南 | 使用文件 |
| `docs/manufacturing_five_level_data_lineage_updated.md` | 製造五階資料血緣 | 業務文件 |

### 📊 日誌和結果
| 檔案 | 用途 | 類型 |
|------|------|------|
| `logs/data_inconsistency_analysis_20260123_143000.md` | 資料不一致分析 | 日誌 |
| `validation_results/dimension_backfill_acceptance_report.md` | 維度補齊驗收報告 | 結果 |

## 第二步：標準專案結構建議

```
dmp_flowable_etl/
├── README.md                    # 專案總覽
├── GETTING_STARTED.md          # 新人快速開始指南
├── ARCHITECTURE.md             # 架構說明
├── package.json                # Node.js依賴
├── docker-compose.yml          # 整體服務編排
│
├── config/                     # 設定檔
│   ├── clickhouse/            # ClickHouse設定
│   ├── cubejs/               # CubeJS設定
│   ├── jdbc-bridge/          # JDBC Bridge設定
│   └── environment/          # 環境變數
│
├── sql/                       # SQL相關
│   ├── ddl/                  # 資料定義語言
│   │   ├── 01_databases.sql
│   │   ├── 02_bronze_layer.sql
│   │   ├── 03_silver_layer.sql
│   │   └── 04_gold_layer.sql
│   ├── dml/                  # 資料操作語言
│   └── validation/           # 驗證查詢
│
├── scripts/                   # 執行腳本
│   ├── setup/               # 安裝設定腳本
│   ├── etl/                 # ETL處理腳本
│   ├── validation/          # 驗證腳本
│   ├── maintenance/         # 維護腳本
│   └── utils/               # 工具腳本
│
├── cubejs/                    # CubeJS資料模型
│   ├── schema/              # 資料模型定義
│   └── config/              # CubeJS設定
│
├── docs/                      # 文件
│   ├── architecture/        # 架構文件
│   ├── user-guides/         # 使用指南
│   ├── api/                 # API文件
│   └── troubleshooting/     # 故障排除
│
├── logs/                      # 日誌
│   ├── etl/                 # ETL日誌
│   ├── validation/          # 驗證日誌
│   └── system/              # 系統日誌
│
├── tests/                     # 測試
│   ├── unit/                # 單元測試
│   ├── integration/         # 整合測試
│   └── e2e/                 # 端到端測試
│
└── monitoring/                # 監控
    ├── dashboards/          # 監控儀表板
    └── alerts/              # 告警設定
```

## 第三步：檔案重新配置建議

### 🔄 需要移動的檔案

#### Scripts 重新分類
```
scripts/setup/
├── install_dependencies.py
└── initialize_database.py

scripts/etl/
├── execute_end_to_end_pipeline.py
├── execute_silver_dimension_update.py
└── execute_gold_dimension_update.py

scripts/validation/
├── verify_mssql_clickhouse_reconciliation.py
├── verify_mview_pipeline_completion.py
└── verify_complete_architecture.py

scripts/maintenance/
├── backup_and_update_silver_mview.py
└── production_environment_test.py

scripts/utils/
├── check_existing_tables.py
├── test_clickhouse_connection.py
└── debug_superset_cne_wj2_nbu_e5_2025_12_25.py
```

#### Config 重新組織
```
config/
├── clickhouse/
│   ├── docker-compose.yml
│   └── config.xml
├── cubejs/
│   ├── .env.example
│   └── docker-compose.yml
├── jdbc-bridge/
│   └── application.properties
└── environment/
    ├── development.env
    ├── staging.env
    └── production.env
```

#### SQL 重新分類
```
sql/
├── ddl/
│   ├── 01_databases.sql
│   ├── 02_bronze_layer.sql
│   ├── 03_silver_layer.sql
│   └── 04_gold_layer.sql
├── dml/
│   ├── dimension_updates/
│   └── data_transformations/
└── validation/
    ├── data_quality_checks.sql
    └── reconciliation_queries.sql
```

#### CubeJS 重新組織
```
cubejs/
├── schema/
│   ├── l5_dashboard_summary.js
│   └── l5_task_completion.js
└── config/
    ├── cube.js
    └── docker-compose.yml
```

## 第四步：新人指南架構

### 📖 文件結構
```
docs/
├── GETTING_STARTED.md         # 新人快速開始
├── ARCHITECTURE.md            # 系統架構
├── DEPLOYMENT.md              # 部署指南
├── API_REFERENCE.md           # API參考
├── TROUBLESHOOTING.md         # 故障排除
└── CHANGELOG.md               # 變更日誌
```

### 🚀 快速開始流程
1. **環境準備** - Docker, Python, Node.js
2. **服務啟動** - MSSQL, ClickHouse, JDBC Bridge, CubeJS
3. **資料初始化** - 執行DDL, 載入初始資料
4. **驗證測試** - 執行端到端測試
5. **儀表板存取** - Superset連接和使用

## 實施建議

### 階段一：基礎重整 (1-2天)
- 建立新的資料夾結構
- 移動現有檔案到對應位置
- 更新所有檔案路徑引用

### 階段二：文件完善 (2-3天)
- 撰寫完整的README和架構文件
- 建立新人指南和部署指南
- 整理API文件和故障排除指南

### 階段三：測試驗證 (1天)
- 驗證所有腳本在新結構下正常運作
- 測試完整的部署流程
- 確認文件的準確性

---

**下一步**: 請確認此結構建議，我將開始執行檔案重整作業。