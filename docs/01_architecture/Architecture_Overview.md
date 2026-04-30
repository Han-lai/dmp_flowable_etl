# DMP Flowable 系統架構總覽

**文件編號**: 01-ARCH-001  
**最後更新**: 2026-04-30  
**狀態**: 正式發布 (Released)  
**維護者**: AIT / Data Engineering

---

## 目錄 (Table of Contents)

1. [系統架構圖](#1-系統架構圖)
2. [完整資料管道](#2-完整資料管道)
3. [各層職責說明](#3-各層職責說明)
4. [ETL 工具鏈三段式架構](#4-etl-工具鏈三段式架構)
5. [應用層拓撲](#5-應用層拓撲)
6. [硬體環境](#6-硬體環境)
7. [相關文件](#7-相關文件)

---

## 1. 系統架構圖

本系統採用三層獎牌架構 (Medallion Architecture)，強調「低延遲查詢」與「高穩定性運算分離」。
資料從 MSSQL 透過原生 ODBC 同步至 ClickHouse，歷經 Bronze → Silver → Gold 三層處理後，由 Serving 層對外提供服務。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MSSQL 來源系統 (Source Layer)                         │
│                                                                             │
│  APP_SRV_BPM (流程引擎)              APP_SRV_COMMON (維度主檔)               │
│  ┌───────────────────────────┐      ┌──────────────────────────────────┐    │
│  │ ACT_HI_TASKINST_0108      │      │ HR_Employee_0202                 │    │
│  │ ACT_HI_VARINST_0108       │      │ EmpNodeRoleMapping_0202          │    │
│  │ ACT_HI_PROCINST_0108      │      │ EmpOrgInfoMapping_0202           │    │
│  │ ACT_HI_IDENTITYLINK_0108  │      │ EmpUserGroupMapping_0202         │    │
│  │ ACT_RE_PROCDEF_0108       │      │ UserGroup_0202                   │    │
│  └───────────────────────────┘      │ ProcessRoleUserMapping_0202      │    │
│                                     │ MDM_LINE_DESC_MASTER_0202        │    │
│                                     │ MDM_PROD_AREA_MASTER_0202        │    │
│                                     │ MDM_FACTORY_AREA_MASTER_0202     │    │
│                                     │ MDM_MFG_SITE_MASTER_0202         │    │
│                                     │ MDM_MFG_PLANT_MASTER_0202        │    │
│                                     │ DMPFunctionConfig_0202           │    │
│                                     │ DMPFunctionClientMapping_0202    │    │
│                                     └──────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼  sync_unified_odbc.py
                                        Native ODBC Driver 18 (Adaptive Batching / Full Sync)
┌─────────────────────────────────────────────────────────────────────────────┐
│  Bronze 層 (ODS 原始資料落地)         ClickHouse Server 76 (REDACTED_IP)    │
│                                                                             │
│  ┌──────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐  │
│  │ BPM 流程核心 (5表)│ │ HR 維度主檔 (6表)      │ │ MDM 製造維度 (7表)     │  │
│  │ bpm_act_hi_      │ │ common_hr_employee    │ │ common_mdm_line_desc  │  │
│  │   taskinst       │ │ common_emp_node_role  │ │ common_mdm_prod_area  │  │
│  │ bpm_act_hi_      │ │ common_emp_org_info   │ │ common_mdm_factory_   │  │
│  │   varinst        │ │ common_emp_user_group │ │   area_master         │  │
│  │ bpm_act_hi_      │ │ common_user_group     │ │ common_mdm_mfg_site   │  │
│  │   procinst       │ │ common_process_role_  │ │ common_mdm_mfg_plant  │  │
│  │ bpm_act_hi_      │ │   user_mapping        │ │ common_dmp_function_  │  │
│  │   identitylink   │ └───────────────────────┘ │   config              │  │
│  │ bpm_act_re_      │                           │ common_dmp_function_  │  │
│  │   procdef        │                           │   client_mapping      │  │
│  └──────────────────┘                           └───────────────────────┘  │
│                                                                             │
│  [水位線追蹤: bronze._sync_watermark]  [Checkpoint: ops_metrics.etl_checkpoint]│
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼  execute_etl.py  Stage 1: EAV Pivot
┌─────────────────────────────────────────────────────────────────────────────┐
│  Silver 層 (DWH 清洗轉換)                                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ mv_varinst_pivoted          (EAV 轉置為寬表: backfill_pivot.sql)    │   │
│  │ mv_dim_mfg_five_level       (五階製造維度: Region→Plant→Factory→Line)│   │
│  │ mv_fact_task_vx             (核心事實表: backfill_silver.sql)        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼  execute_etl.py  Stage 2: Metric Aggregation
┌─────────────────────────────────────────────────────────────────────────────┐
│  Gold 層 (KPI 物理化指標)                                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ rmv_l5_milestone_phys       (里程碑: Todo/Doing/Done 快照)          │   │
│  │ rmv_l5_acc_phys             (累積在途量: 7日滾動 uniqExact)         │   │
│  │ rmv_l5_task_completion_phys (最終合併主表: FULL OUTER JOIN)         │   │
│  │ rmv_l5_task_completion      (BI 對接視圖: VIEW + FINAL)             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Serving 層 (應用服務)                                                       │
│                                                                             │
│  ┌───────────────┐  ┌────────────────────────┐  ┌──────────────────────┐   │
│  │   Cube.js     │  │   FastAPI (Python)      │  │   Spring Boot (Java) │   │
│  │  ─────────── │  │  ──────────────────────│  │ ────────────────────│   │
│  │  語意模型層   │  │  api/main.py            │  │  業務 CRUD / 跨系統  │   │
│  │  查詢快取     │  │  L5 任務完成率 API 服務  │  │  資料對接            │   │
│  │  Pre-agg     │  │  GET/POST /api/l5/      │  │                      │   │
│  └──────┬────────┘  └──────────┬─────────────┘  └──────────┬───────────┘   │
│         │                      │                            │               │
│         └──────────────────────┼────────────────────────────┘               │
│                                ▼                                            │
│                     ┌──────────────────┐                                    │
│                     │   Node.js        │                                    │
│                     │  ──────────────  │                                    │
│                     │  Auth 認證 /     │                                    │
│                     │  API 路由轉發    │                                    │
│                     └──────────────────┘                                    │
│                                │                                            │
│                                ▼                                            │
│                     BI Dashboard / Client                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 完整資料管道

以下為系統各元件間的資料流向關係：

```
MSSQL APP_SRV_BPM ──────────────┐
                                 │
MSSQL APP_SRV_COMMON ───────────┼──► sync_unified_odbc.py ──► Bronze 層 (18 張表)
                                 │         (ODBC Driver 18)         │
                                 │                                   │
                                 │                          ┌────────▼─────────┐
                                 │                          │  bpm_act_hi_     │
                                 │                          │  varinst         │
                                 │                          └────────┬─────────┘
                                 │                                   │
                                 │                          execute_etl.py Stage 1
                                 │                                   │
                                 │                          ┌────────▼─────────┐
                                 │                          │ mv_varinst_      │
                                 │                          │ pivoted (Silver) │
                                 │                          └────────┬─────────┘
                                 │                                   │
                                 │              ┌────────────────────┤
                                 │              │                    │
                                 │   bpm_act_   │            mv_dim_mfg_
                                 │   hi_taskinst│            five_level
                                 │   (Bronze)   │            (Silver Dim)
                                 │              │                    │
                                 │              └────────────────────┤
                                 │                                   │
                                 │                          execute_etl.py Stage 2
                                 │                                   │
                                 │                          ┌────────▼─────────┐
                                 │                          │ mv_fact_task_vx  │
                                 │                          │ (Silver Fact)    │
                                 │                          └────────┬─────────┘
                                 │                    ┌─────────────┤
                                 │                    │             │
                                 │           ┌────────▼──┐  ┌───────▼──────┐
                                 │           │ milestone │  │ acc_phys     │
                                 │           │ _phys     │  │ (7日滾動)    │
                                 │           └────────┬──┘  └───────┬──────┘
                                 │                    └──────┬───────┘
                                 │                           │ FULL OUTER JOIN
                                 │                  ┌────────▼────────────┐
                                 │                  │ task_completion_    │
                                 │                  │ phys (Gold 主表)    │
                                 │                  └────────┬────────────┘
                                 │                           │ VIEW + FINAL
                                 │                  ┌────────▼────────────┐
                                 │                  │ rmv_l5_task_        │
                                 │                  │ completion (View)   │
                                 │                  └────────┬────────────┘
                                 │                           │
                                 │             ┌─────────────┼──────────────┐
                                 │             │             │              │
                                 │      Cube.js REST   FastAPI /api   Spring Boot
                                 │             │             │              │
                                 │             └─────────────┼──────────────┘
                                 │                           │
                                 │                    Node.js (Auth/Route)
                                 │                           │
                                 └─────────────────► BI Dashboard / Client
```

---

## 3. 各層職責說明

### 3.1 Bronze 層 (原始資料落地)

| 屬性           | 說明                                                                 |
| :------------- | :------------------------------------------------------------------- |
| **職責**       | 忠實複製來源資料，保留來源端全貌，不做任何業務轉換                   |
| **儲存引擎**   | `ReplacingMergeTree(_sync_version)`                                  |
| **資料庫**     | `bronze`                                                             |
| **表格數量**   | 共 18 張表 (BPM 流程核心 5 表 + HR 維度 6 表 + MDM 製造維度 7 表)   |
| **寫入策略**   | 批次增量 (`batch`) 或全量清除後重寫 (`full`)                         |
| **增量追蹤**   | `bronze._sync_watermark` — 記錄各表最後同步時間與累計筆數            |
| **索引優化**   | `bpm_act_hi_taskinst` 對 `START_TIME_` 建 minmax 索引；`bpm_act_hi_varinst` 對 `TASK_ID_` 建 bloom_filter 索引 |

**全量同步表** (每次 TRUNCATE → 全量寫入)：HR 員工主檔、Emp 映射表群、MDM 五階製造維度群、DMP 功能配置表。

**增量同步表** (依時間欄位分批批次)：`ACT_HI_TASKINST`、`ACT_HI_VARINST`、`ACT_HI_PROCINST`、`ACT_HI_IDENTITYLINK`。

---

### 3.2 Silver 層 (清洗轉換)

| 屬性         | 說明                                                          |
| :----------- | :------------------------------------------------------------ |
| **職責**     | EAV 轉置、Vx 版本歸屬判定、排除規則標記、五階維度整合          |
| **儲存引擎** | `ReplacingMergeTree(_mview_update_time)`                      |
| **資料庫**   | `silver`                                                      |

**Stage 1 — EAV Pivot** (`backfill_pivot.sql`)

將 `ACT_HI_VARINST` 的 EAV 格式轉置為寬表 (`mv_varinst_pivoted`)，使流程變數 (`region`、`plant`、`moNumber` 等) 可作為欄位直接 JOIN 使用。

**Stage 2 — 事實表建構** (`backfill_silver.sql` + `backfill_exclusion.sql`)

- **Vx 歸屬邏輯**：依特定工單號前綴 (196, 199, 200, 210, 212, 213) 強制歸類為 V1，再依 `TASK_DEF_KEY_` 前綴自動判定 V1/V2/V3。
- **排除規則**：自動標記 `autoComplete=1`、`E%`/`C%` 系統節點、`Q%`/`R%` 測試工單、`Notify`/`Dummy` 佔位任務。

---

### 3.3 Gold 層 (物理化 KPI)

| 屬性         | 說明                                                              |
| :----------- | :---------------------------------------------------------------- |
| **職責**     | 業務指標聚合、物理化快照，將耗能運算移至 ETL 批次，查詢端記憶體 < 5 MiB |
| **儲存引擎** | `ReplacingMergeTree(_refresh_time)`                               |
| **資料庫**   | `gold`                                                            |

| 物理表 / 視圖                    | Stage | 說明                                        |
| :------------------------------- | :---: | :------------------------------------------ |
| `rmv_l5_milestone_phys`          |   4   | Todo / Doing / Done 快照計數                |
| `rmv_l5_acc_phys`                |   5   | 7 日滾動 `uniqExact` 在途任務去重           |
| `rmv_l5_task_completion_phys`    |   6   | FULL OUTER JOIN 合併主表                    |
| `rmv_l5_task_completion` (View)  |  —    | BI 對接視圖，加 `FINAL` 確保 ReplacingMergeTree 去重完成 |

**設計動機**：系統最初於 Server 207 (充裕記憶體) 採用 Refreshable Materialized View 架構。遷移至 Server 76 (Docker 11 GiB RAM，可用約 6 GiB) 後，即時聚合觸發 OOM，因此改為「物理化分離聚合架構」，以穩定查詢層資源消耗。

---

## 4. ETL 工具鏈三段式架構

系統由三支 Python 腳本構成完整的部署與執行管線，各自職責獨立：

```
  ┌───────────────────────────────────────────────────────────────────────┐
  │                       ETL 工具鏈執行順序                               │
  │                                                                       │
  │  Step 1                Step 2                    Step 3               │
  │  ─────────────         ──────────────────         ─────────────────── │
  │  setup_schema.py  ──►  sync_unified_odbc.py  ──►  execute_etl.py      │
  │                                                                       │
  │  建立DB與表結構          MSSQL → Bronze 抽取         Silver/Gold 運算    │
  │  讀取 infra_config.yaml  讀取 sync_tables.yaml       讀取 pipeline_      │
  │  執行 sql/etl/schema/   Adaptive Batching          config.yaml         │
  │  00~06 DDL 檔           Watermark 追蹤              時間視窗批次         │
  │                         18 張表同步                 Checkpoint 斷點續傳  │
  └───────────────────────────────────────────────────────────────────────┘
```

**設定檔對應關係**：

```
scripts/etl/config/
├── infra_config.yaml       ◄── setup_schema.py 讀取
│   (資料庫清單 + DDL 執行順序)
│
├── sync_tables.yaml        ◄── sync_unified_odbc.py 讀取
│   (18 張表的來源 / 目標 / 欄位型別 / 同步策略)
│
└── pipeline_config.yaml    ◄── execute_etl.py 讀取
    (Silver→Gold 的階段順序 + SQL 模板名稱 + reset_targets)
```

**常用指令**：

```bash
# 基礎建設部署 (首次或 Schema 變更時執行)
python scripts/etl/setup_schema.py

# ODBC 資料同步 (同步所有 18 張表)
python scripts/etl/sync_unified_odbc.py

# 歷史補分 (指定日期範圍，低記憶體模式)
python scripts/etl/execute_etl.py --backfill --start 2025-01-01 --low-ram --step-days 10

# 每日增量更新 (自動回溯最近 7 天)
python scripts/etl/execute_etl.py --daily --low-ram

# 查看管線狀態 (Watermark / Checkpoint / 各表列數)
python scripts/etl/execute_etl.py --status
```

---

## 5. 應用層拓撲

```
  Gold Layer (ClickHouse)
          │
          │  gold.rmv_l5_task_completion (View)
          │
   ┌──────┴──────────────────────────────────────────────┐
   │                                                     │
   ▼                                                     ▼
Cube.js (port 4002/4003)                       FastAPI (api/main.py)
─────────────────────────                      ──────────────────────
語意模型 (Semantic Model)                       GET/POST /api/l5/task-report
查詢快取 / Pre-aggregation                      直接讀取 Gold 視圖
Row-Level Security (DSC)                       適合後端程式對接
   │                                                     │
   └──────────────────────┬──────────────────────────────┘
                          │
               Spring Boot (業務 CRUD / 跨系統對接)
                          │
                          ▼
                     Node.js
                ──────────────────
                Auth 認證 (JWT/SSO)
                API 路由轉發
                          │
                          ▼
               BI Dashboard / Client
```

**設計原則**：ClickHouse 不直接對外暴露，所有查詢流量均先經過 Cube.js 查詢合併與快取，以確保 Server 76 在 100 人同時存取時的系統穩定性。

---

## 6. 硬體環境

| 項目              | 規格                                              |
| :---------------- | :------------------------------------------------ |
| **目標伺服器**    | REDACTED_IP (Docker 容器)                       |
| **部署記憶體**    | 11 GiB (實際可用約 6 GiB，需預留 OS 與 Buffer)    |
| **ClickHouse 版本** | v25.8                                           |
| **資料驅動**      | Microsoft ODBC Driver 18 for SQL Server           |
| **併發保護**      | `max_concurrent_queries = 50` / `queue_max_wait_ms = 30000` |
| **ETL 記憶體上限** | `max_memory_usage = 5.5 GiB` (低記憶體模式)      |
| **日誌資料庫**    | `ops_metrics` (存放 ETL Checkpoint 紀錄)         |

---

## 7. 相關文件

| 文件                                         | 路徑                                                     |
| :------------------------------------------- | :------------------------------------------------------- |
| ODBC 驅動配置手冊                            | `docs/01_architecture/ClickHouse_ODBC_Setup.md`       |
| 部署指南                                     | `docs/02_deployment/Deployment_Guide.md`              |
| 同步引擎與水位線操作說明                     | `docs/02_deployment/Deployment_Guide.md` |
| 效能壓測報告 (Gold 層實體化驗收)             | `docs/05_monitoring/Physical_Gold_Benchmark_Report.md` |
| 完整技術設計文件                             | `docs/DMP_Flowable_Technical_Documentation.md`           |

---

**文件負責人**: AIT / Data Engineering  
**審核狀態**: 已對照現行程式碼 (`sync_tables.yaml`、`pipeline_config.yaml`、`infra_config.yaml`、`execute_etl.py`、`api/main.py`) 驗證完成
