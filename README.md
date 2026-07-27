# DMP Flowable 流程分析系統 (DMP Flowable Process Analytics)

本專案是一套基於 **Flowable BPM** 的自動化資料流與數據分析系統。核心目標是將分散的 BPM 流程簽核數據，透過 ETL Pipeline 整合至 ClickHouse 物理化數據倉儲，產出量化的生產管理指標（如：L5 任務完成率、累積在途量 ACC），為製造業產線管理層提供即時的數據決策支援。

---

## 1. 系統架構亮點 (Architecture Highlights)

採用獎牌架構（Medallion）三層數倉，因應正式環境（Docker 11 GiB，可用約 6 GiB）記憶體限制，全面物理化聚合、以時間視窗批次運算取代即時查詢：

* **Bronze 層**：以顯式 Schema 的 `ENGINE=ODBC` 表同步 MSSQL（19 張表），繞過 driver 自動探測在 LOB 欄位上的死鎖；`watermark` 表追蹤同步進度與真實資料時間跨度。
* **Silver 層**：EAV 變數轉置（Pivot）+ 五階製造維度對齊，統一寫入單一事實表 `silver.mv_fact_task_vx`（Super Silver，KPI 與明細共用同一真相來源）。
* **Gold 層**：以 `groupBitmapStateIf` 產生 Todo/Doing/Done 快照與 7 日滾動 ACC，全面避免耗能的 `ARRAY JOIN`；再由雙管線預聚合彙總表 `gold.rmv_l5_task_summary`（`2026-04-01` 前後分別走 V3/V4 邏輯）把 Bitmap 轉為整數，Cube.js 查詢降為純 `SUM` 運算，單次指標查詢耗時從 30+ 秒降至 0.06~0.11 秒。
* **Cube.js 語意層閘道**：全面禁止前端直連資料庫，SQL 翻譯 + 結果快取，將資料庫負載降低逾 98%。

---

## 2. 資料管線 (ETL Pipeline)

三支 Python 引擎依序執行，各自讀取獨立的 YAML 設定檔，職責分離：

| 引擎 | 職責 | 設定檔 |
|---|---|---|
| `scripts/etl/setup_schema.py` | 建立資料庫與部署 DDL（bronze/silver/gold/ops_metrics） | `scripts/etl/config/infra_config.yaml` |
| `scripts/etl/sync_unified_odbc.py` | MSSQL → Bronze 同步（19 張表，watermark 斷點續傳） | `scripts/etl/config/sync_tables.yaml` |
| `scripts/etl/execute_etl.py` | Silver/Gold 運算（8 個 phase，checkpoint 斷點續傳） | `scripts/etl/config/pipeline_config.yaml` |

業務邏輯全部以 SQL 模板形式存放在 `sql/etl/dml/`（Pivot → Silver Facts → Exclusion → Milestone → ACC → Unified → Summary Historical → Summary），以 `{start_ts}`/`{end_ts}` 佔位符做時間視窗批次替換。

---

## 3. 快速上手 (Quick Start)

```powershell
# 1. 基礎架構部署（首次部署或 Schema 變更時執行）
python scripts/etl/setup_schema.py

# 2. Bronze 資料抽取同步（MSSQL → ClickHouse，支援 Watermark 斷點續傳）
python scripts/etl/sync_unified_odbc.py --table all

# 3. Silver/Gold 每日增量運算（自動接龍回溯異動範圍）
python scripts/etl/execute_etl.py --daily --low-ram

# 3b. 歷史區間回填
python scripts/etl/execute_etl.py --backfill --start 2025-01-01 --end 2025-01-31 --low-ram --step-days 10

# 生產環境健康檢查（水位線 / Checkpoint / 各表筆數）
python scripts/etl/execute_etl.py --status

# 單元測試
python -m pytest tests/ -v
```

---

## 4. 效能優化里程碑 (Performance Results)

* **抽取**：以 Native ODBC 取代 JDBC Bridge，5,300 萬筆資料可於分鐘級完成搬運。
* **Gold 預聚合**：透過 `gold.rmv_l5_task_summary` 整數彙總表，Cube.js 前端查詢從 30+ 秒（超時）降至 **0.06~0.11 秒**，時間與空間複雜度由 O(N²) 降為 O(1)。
* **百人併發**：`clickhouse-benchmark` 實測顯示高併發下無 OOM。

---

## 5. 專案結構 (Project Structure)

```text
dmp_flowable/
├── api/
│   └── main.py                 # FastAPI L5 報表 API（port 7088）
├── cube/
│   └── model/
│       ├── cubes/               # Cube.js 語意模型（L5TaskPeriodic / Pivot / Details）
│       └── views/               # Cube.js 歷史趨勢 view
├── docs/                       # 技術文件庫（架構/部署/指標/展示層/監控/交接手冊）
├── infra/                      # docker-compose 部署設定（api / cube / monitoring / clickhouse）
├── memory-bank/                 # 專案工作記憶（當前焦點、進度、技術決策）
├── scripts/
│   ├── etl/
│   │   ├── setup_schema.py      # DDL 結構部署
│   │   ├── sync_unified_odbc.py # Bronze 層 ODBC 同步引擎
│   │   ├── execute_etl.py       # Silver/Gold 運算主程式
│   │   └── config/               # 三個 YAML 設定檔
│   └── export/                  # 明細匯出工具
├── sql/
│   └── etl/
│       ├── schema/               # 各層 DDL 定義（00~07）
│       └── dml/                  # 各階段轉換 SQL 模板
└── tests/                       # pytest 單元測試
```

---

## 6. 核心業務規則摘要

* **五階維度**：Region → Plant → Factory → Line（+ vx_type），優先取流程變數，其次以 MDM 主檔回推，皆查不到則保留空字串（不填 UNKNOWN）。
* **vx_type 判定**：NPE 廠區任務優先歸 V1（V2 出貨行政任務除外）→ 特定工單前綴（196/199/200/210/212/213）歸 V1 → 依 `TASK_DEF_KEY_` 前綴判斷 V1/V2/V3。
* **Cohort 結算**：任務以「開單日」錨定，日/週/月三種粒度各自在期末評估完工狀態，避免跨期重複計數。
* **ACC（累積在途量）**：日粒度採 7 日滾動去重計數；週/月粒度採期末 todo+doing。
* **排除規則**：autoComplete=1、SYSTEM 帳號、系統節點（E/C 開頭）、Q/R 測試工單、Notify/Dummy 任務一律排除於 KPI 統計外。
* **費率顯示**：一律無條件捨去取整數百分比（`floor(qty*100/total)`），不用四捨五入。

---

**維護規則**：MSSQL 來源庫為生產環境，嚴禁任何寫入/DDL 操作。連線資訊一律透過環境變數提供，程式碼與文件不得寫死內部 IP 或密碼。
