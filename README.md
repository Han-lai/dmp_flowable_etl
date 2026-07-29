# DMP Flowable 流程分析系統

[![ClickHouse](https://img.shields.io/badge/ClickHouse-25.8-FFCC01?logo=clickhouse&logoColor=black)](https://clickhouse.com/)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Cube.js](https://img.shields.io/badge/Cube.js-semantic%20layer-orange)](https://cube.dev/)
[![Status](https://img.shields.io/badge/status-production-brightgreen)]()

基於 **Flowable BPM** 的自動化資料流與數據分析系統。將分散的 BPM 流程簽核數據透過 ETL Pipeline 整合至 ClickHouse 數據倉儲，產出量化的生產管理指標（L5 任務完成率、累積在途量 ACC 等），供製造業產線管理層即時查詢決策。

> **完整技術文件請見 [`docs/SYSTEM_REFERENCE.md`](docs/SYSTEM_REFERENCE.md)** — 架構設計、業務邏輯、部署與維運指令的唯一依據。本 README 僅提供專案總覽與快速上手。

---

## 目錄

- [系統架構](#系統架構)
- [技術棧](#技術棧)
- [快速開始](#快速開始)
- [專案結構](#專案結構)
- [核心業務規則](#核心業務規則)
- [文件索引](#文件索引)
- [維運鐵律](#維運鐵律)

---

## 系統架構

```
MSSQL（唯讀來源） → ODBC → ClickHouse（bronze → silver → gold） → Cube.js（語義層） → 前端 BI
```

採獎牌架構（Medallion）三層數倉：

- **Bronze**：以顯式 Schema 的 `ENGINE=ODBC` 表同步 MSSQL（19 張表），繞過 driver 自動探測在 LOB 欄位上的死鎖；`_sync_watermark` 表追蹤同步進度與真實資料時間跨度。
- **Silver**：EAV 變數轉置（Pivot）+ 五階製造維度對齊，統一寫入單一事實表 `silver.mv_fact_task_vx`。
- **Gold**：以 Bitmap 運算產生 Todo/Doing/Done 快照與滾動 ACC，再由預聚合彙總表 `gold.rmv_l5_task_summary` 轉為整數，Cube.js 查詢降為純 `SUM` 運算。
- **Cube.js**：唯一對外語義層，禁止前端直連資料庫。

詳細架構圖、模組職責、雙管線邊界等說明見 [`docs/SYSTEM_REFERENCE.md`](docs/SYSTEM_REFERENCE.md)。

---

## 技術棧

| 項目 | 版本／規格 |
|---|---|
| ClickHouse | 25.8.18.1（客製 image，內建 Native ODBC） |
| ODBC 連線 | Native C++ ODBC Bridge |
| Python | 3.x（`clickhouse-connect`、`pyyaml`、`pandas`） |
| Cube.js | 容器化部署 |
| 部署方式 | Docker Compose（split-stack，各服務獨立 compose） |

---

## 快速開始

```bash
# 0. 載入環境變數（infra/.env 需自行建立，見 docs/SYSTEM_REFERENCE.md §3.1）
set -a && . infra/.env && set +a

# 1. 啟動 ClickHouse
docker-compose -f infra/clickhouse/odbc/docker-compose-odbc.yml up -d

# 2. 初次建置：部署 schema + 同步 MSSQL + 回填 silver/gold（唯一入口）
export MSSQL_USER=APP_SRV_BPM
export MSSQL_PASSWORD=<MSSQL 密碼>
./scripts/etl/init_pipeline.sh

# 3. 啟動 Cube.js 語義層
docker-compose -f infra/cube/docker-compose.yml up -d

# 4. 健康檢查
python scripts/etl/execute_etl.py --status

# 5. 單元測試
python -m pytest tests/ -v
```

日常增量由 `scripts/etl/daily_etl_wrapper.sh` 排程執行（cron，建議每日凌晨）。逐月回填、單一 phase 執行等進階用法見 [`docs/SYSTEM_REFERENCE.md` §3.3](docs/SYSTEM_REFERENCE.md#33-初次建置唯一入口-init_pipelinesh)。

---

## 專案結構

```text
dmp_flowable/
├── api/                          # FastAPI 服務
├── cube/
│   └── model/
│       ├── cubes/                 # Cube.js 語意模型（L5TaskPeriodic 等）
│       └── views/                 # Cube.js view
├── docs/
│   ├── SYSTEM_REFERENCE.md        # ★ 唯一技術文件依據
│   └── archive/                   # 已過時的歷史文件
├── infra/                        # docker-compose 部署設定（clickhouse / cube / api / monitoring）
├── memory-bank/                   # 專案工作記憶
├── scripts/
│   ├── etl/
│   │   ├── init_pipeline.sh       # 初次建置／分階段執行入口
│   │   ├── daily_etl_wrapper.sh   # 每日排程入口
│   │   ├── setup_schema.py        # DDL 結構部署
│   │   ├── sync_unified_odbc.py   # Bronze 層 ODBC 同步引擎
│   │   ├── execute_etl.py         # Silver/Gold 運算主程式
│   │   └── config/                # YAML 設定檔
│   └── export/                    # 明細匯出工具
├── sql/
│   └── etl/
│       ├── schema/
│       │   ├── 00_meta_checkpoint.sql
│       │   ├── 01_bronze_flowable_core.sql
│       │   ├── 02_bronze_common_dims.sql
│       │   ├── 03_silver_pivot_and_hierarchy.sql
│       │   ├── 04_silver_fact_tasks.sql
│       │   ├── 06_gold_kpi_task_completion.sql
│       │   └── 06b_gold_kpi_task_summary.sql
│       └── dml/
│           ├── backfill_pivot.sql                    # phase: silver_varinst_pivoted
│           ├── backfill_silver.sql                   # phase: silver_facts
│           ├── backfill_exclusion.sql                # phase: silver_exclusion
│           ├── backfill_gold_milestone.sql           # phase: gold_milestone
│           ├── backfill_gold_acc.sql                 # phase: gold_acc
│           ├── backfill_gold.sql                     # phase: gold_unified
│           ├── backfill_gold_summary_historical.sql  # phase: gold_summary_historical
│           ├── backfill_gold_summary.sql             # phase: gold_summary
│           └── init_dim_mfg_five_level.sql           # 五階維度重建（隨 Bronze 全量同步觸發）
└── tests/                        # pytest 單元測試
```

---

## 核心業務規則

- **五階維度**：Region → Plant → Factory → Line（+ vx_type），優先取流程變數，其次以 MDM 主檔回推。
- **Cohort 結算**：任務以「開單日」錨定，日/週/月三種粒度各自在期末評估完工狀態。
- **費率計算**：一律 `floor(qty*100/total)`，不用四捨五入。
- **排除規則**：`autoComplete=1`、`SYSTEM` 帳號、系統節點、Q/R 測試工單、Notify/Dummy 任務排除於 KPI 統計外。

完整規則定義（含雙管線邊界、例外處理、watermark 機制）見 [`docs/SYSTEM_REFERENCE.md` §2](docs/SYSTEM_REFERENCE.md#2-業務邏輯)。

---

## 文件索引

| 文件 | 用途 |
|---|---|
| [`docs/SYSTEM_REFERENCE.md`](docs/SYSTEM_REFERENCE.md) | **唯一技術文件依據**：架構、業務邏輯、部署指令 |
| [`docs/CLICKHOUSE_INFRA.md`](docs/CLICKHOUSE_INFRA.md) | ClickHouse 容器建置：客製 image、ODBC 設定、server/user 層級設定檔 |
| [`docs/archive/`](docs/archive/) | 已過時的歷史文件，僅供追溯 |

---

## 維運鐵律

- **MSSQL 來源庫唯讀**，嚴禁任何寫入／DDL 操作。
- **連線資訊一律環境變數**（`infra/.env`），程式碼與文件不得寫死內部 IP 或密碼。
- `--reset` / `TRUNCATE` / `DROP` 類操作務必事先確認。
