# 專案結構說明 (Project Structure)

**版本**: 3.0 (目錄整理完成版)  
**更新日期**: 2026-02-24

---

##  專案結構

```
dmp_flowable/
│
├── README.md                        # 專案總覽
├── PROJECT_STRUCTURE.md             # 本檔案
├── PROJECT_AUDIT_REPORT.md          # 專案審核報告
├── .gitignore
├── package.json
│
├── config/                          #  環境設定
│   └── environments/
│       ├── development.env.example  # 開發環境範本
│       ├── production.env.example   # 正式環境範本
│       └── .env.validation          # 驗證環境
│
├── docker/                          # 🐋 基礎設施
│   ├── docker-compose.yml           # ClickHouse + JDBC Bridge 部署
│   ├── clickhouse/config/           # ClickHouse 設定
│   └── jdbc-bridge/                 # JDBC Bridge 設定 + 驅動
│
├── sql/                             #  資料庫定義 (Source of Truth)
│   ├── setup/
│   │   └── 00_init_databases.sql    # 初始化 bronze/silver/gold DB
│   ├── etl/                     # Bronze → Silver → Gold 完整管線
│   │   ├── 01_bronze_flowable_core.sql
│   │   ├── 02_bronze_common_dims.sql
│   │   ├── 03_silver_pivot_and_hierarchy.sql
│   │   ├── 04_silver_fact_tasks.sql
│   │   ├── 05_silver_dim_users.sql
│   │   ├── 06_gold_kpi_task_completion.sql
│   │   ├── 07_gold_kpi_user_utilization.sql
│   │   └── dynamic_periodic_report.sql
│   └── verification/
│       └── 06_validation.sql        # 驗證查詢
│
├── scripts/                         #  執行腳本
│   ├── etl/                     #  生產同步 (核心)
│   │   ├── sync_unified.py          # 統一同步腳本 (主力)
│   │   ├── sync_batches_consolidated.py
│   │   ├── execute_etl.py       # 完整重建
│   │   ├── execute_sql.py           # 通用 SQL 執行器
│   │   ├── generate_full_bronze_ddl.py
│   │   ├── check_sync_status.py
│   │   └── update_mviews_no_data_loss.py
│   │
│   ├── setup/                       #  一次性設定
│   │   ├── create_bronze_tables.py
│   │   └── create_safe_user.py
│   │
│   └── validation/                  #  驗證腳本 (開發過程產物)
│       ├── date_audit/      (23)    # 日期特定 & 月份稽核
│       ├── infra_check/     (16)    # 連線、DDL、表格、帳號檢查
│       ├── data_explore/    (13)    # 維度、任務狀態、人員探索
│       ├── logic_verify/    (11)    # 核心/複雜/嚴格規則驗證
│       ├── gold_layer/      (10)    # Gold 層建立、修復、診斷
│       ├── l5_l7/           (9)     # L5/L7 指標驗證
│       └── debug/           (4)     # 除錯腳本
│
├── cube/                            #  Cube.js 語意層
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── README.md
│   └── model/
│       ├── cubes/
│       │   ├── cube_l5_task_periodic_v2.js        # L5 V2 模型 (active)
│       │   ├── cube_l5_task_periodic_v2_pivot.js   # L5 V2 Pivot (active)
│       │   ├── README_L5_DASHBOARD_CUBE.md
│       │   └── archive/             # 已棄用的舊版模型 (5)
│       └── views/
│           └── view_historical_trends.js
│
├── docs/                            #  技術文檔
│   ├── 00_INDEX.md                  # 文檔索引
│   ├── 01_Architecture_Overview.md
│   ├── 01b_System_Flow_Diagram.md
│   ├── 02_E2E_Implementation_Guide.md
│   ├── 03_1_columns_defin.md
│   ├── 03_Business_Metric_Definitions.md
│   ├── 04_Data_Lineage_Mapping.md
│   ├── 05_Field_Verification_Reference.md
│   ├── 06_Technical_Deep_Dive_MViews.md
│   ├── L5_Completion_Superset_Guide.md
│   ├── L5_Periodic_Report_V2_Flow.md
│   ├── missing_tables_analysis.md
│   ├── guides/                      # 操作指南
│   ├── specs/                       # 指標規格 (L5, L7)
│   ├── reports/                     # 報告紀錄
│   └── refrence_sql/                # 參考 SQL & DDL 快照
│
├── logs/                            #  日誌與輸出
│   ├── output/                      # 驗證過程的輸出紀錄 (16)
│   └── daily_reports/
│
└── memory-bank/                     #  AI 記憶庫
    ├── activeContext.md
    ├── productContext.md
    ├── progress.md
    ├── projectbrief.md
    ├── systemPatterns.md
    └── techContext.md
```

---

##  核心模組速覽

| 模組 | 路徑 | 用途 |
|------|------|------|
| Docker 部署 | `docker/` | ClickHouse + JDBC Bridge 基礎設施 |
| SQL 管線 | `sql/etl/` | Bronze → Silver → Gold 三層資料轉換 |
| 同步腳本 | `scripts/etl/` | 生產環境資料同步與重建 |
| Cube.js | `cube/` | 語意層模型，驅動 Superset 儀表板 |
| 環境設定 | `config/environments/` | 開發 / 正式環境參數 |
| 技術文檔 | `docs/` | 架構、指標定義、操作指南 |

---

## 📂 目錄分類

###  生產必要 (~45 檔案)
`docker/`, `sql/`, `scripts/etl/`, `cube/`, `config/`, 核心文件

###  開發過程產物 (~86 檔案)
`scripts/validation/` 全部子目錄 — 驗證邏輯正確性的一次性腳本

###  日誌與紀錄 (~20 檔案)
`logs/` — 各階段的輸出與報告

---

**最後更新**: 2026-02-24  
**版本**: 3.0 (目錄整理完成版)