# DMP Flowable 部署與 ETL 維運手冊 (ODBC 版)

**文件編號**: 02-DEP-001  
**版本**: 5.1 (合併版 — 含 ETL 同步引擎與 Watermark 運維)  
**最後更新**: 2026-05-28  
**定位**: 本文件提供基於 ODBC 架構的系統部署、資料同步與 ETL 運維完整指南。

---

## 1. 系統架構簡述 (Architecture Summary)

本系統採用 **Native ODBC** 進行數據同步，並實施 **物理化金層 (Physical Gold Layer)** 以確保在資源受限環境 (6GB RAM) 下的穩定性。

核心腳本職責分工：

| 腳本 | 職責 |
| :--- | :--- |
| `setup_schema.py` | 初始化各層資料庫、資料表與 DDL |
| `sync_unified_odbc.py` | MSSQL → ClickHouse Bronze 層數據同步 (含 Watermark 控制) |
| `execute_etl.py` | Bronze → Silver → Gold 分析計算與物理化儲存 |

---

## 2. 環境準備與部署 (Environment & Deployment)

### 2.1 目錄結構
```text
dmp_flowable/
├── infra/                      # 基礎設施配置中心
│   ├── .env                    # 通用環境變數
│   ├── clickhouse/             # ClickHouse 堆疊 (docker-compose.yml)
│   └── api/                    # API 堆疊 (docker-compose.yml)
├── api/                        # API 原始碼
├── scripts/etl/                # 核心 ETL 腳本
│   ├── setup_schema.py
│   ├── sync_unified_odbc.py
│   └── execute_etl.py
└── sql/etl/                    # 初始化與轉換 SQL
```

### 2.2 啟動步驟

#### 第一步：啟動 ClickHouse 核心
```bash
docker-compose -f infra/clickhouse/docker-compose.yml up -d
```

#### 第二步：啟動 API 服務
```bash
docker-compose -f infra/api/docker-compose.yml up -d
```

#### 第三步：初始化資料管線
```bash
# 步驟 3-1: 建立各層級資料庫、表結構與 DDL
python scripts/etl/setup_schema.py

# 步驟 3-2: 執行數據同步 (MSSQL → Bronze)
python scripts/etl/sync_unified_odbc.py --table all

# 步驟 3-3: 執行分析計算 (Bronze → Silver → Gold)
python scripts/etl/execute_etl.py --daily --low-ram
```

---

## 3. ETL 同步引擎：`sync_unified_odbc.py`

這是目前的數據搬運核心，支援「全量」與「增量批次」兩大策略，並針對 Server 76 的記憶體限制進行了適應性調整。

### 3.1 資料表同步配置 (`load_configs()`)
配置位於 `config/sync_tables.yaml`，定義每張 MSSQL 來源表的同步策略（全量 / 增量）與時間戳欄位。

### 3.2 顯式 DDL 機制
腳本在同步時會動態建立臨時的 ODBC Engine 表，並注入顯式的 DDL schema，以避開自動偵測造成的大型欄位死鎖。

### 3.3 增量過濾邏輯
系統直接在 ClickHouse 建立 `bronze._sync_watermark` 表追蹤同步進度（不依賴外部狀態）。增量 SQL 執行模式如下：

```sql
INSERT INTO {target}
SELECT {cols}, now() as _extracted_at
FROM odbc_temp_engine
WHERE {time_col} >= '{start_str}' AND {time_col} < '{end_str}'
```

### 3.4 適應性分批 (Adaptive Batching)
若發生 OOM 或超時，腳本會自動將時間區間減半重試。若需調整重試深度，請查閱代碼中的 `sync_batch_adaptive` 邏輯。

---

## 4. Watermark 機制維護

系統以 `bronze._sync_watermark` 表作為增量同步的狀態中心。

### 4.1 查詢當前 Watermark 狀態
```sql
SELECT table_name, last_sync_time, sync_mode
FROM bronze._sync_watermark
ORDER BY table_name;
```

### 4.2 手動重置 Watermark（強制重刷特定表）
```bash
python scripts/etl/sync_unified_odbc.py --table taskinst --start "2025-01-01"
```

---

## 5. 故障排除與維運 (Troubleshooting)

| 現象 | 可能原因 | 排除方法 |
| :--- | :--- | :--- |
| **ODBC 連線失敗** | DSN 未配置 | 檢查系統 ODBC DSN 是否存在 `MSSQL_DSN` |
| **ETL 記憶體溢出 (OOM)** | 資源限制 | 使用 `--low-ram` 並調小 `--step-days` |
| **增量同步資料缺口** | Watermark 狀態錯誤 | 手動指定 `--start` 日期重新補刷 |
| **同步超時 Timeout** | 分批過大 | Adaptive Batching 自動減半，或手動調小 `--step-days` |

---

## 6. 全新環境部署 SOP (From-Scratch Setup)

以下是從零搭建完整系統的步驟，適用於首次部署或遷移至新主機。

### 6.1 環境準備

```powershell
# 建立 Python 虛擬環境
python -m venv .venv
.venv\Scripts\Activate.ps1

# 安裝依賴
pip install clickhouse-connect pyodbc pyyaml
```

**前置條件**：
- ClickHouse Server 已啟動（含 ODBC Bridge 容器）
- MSSQL ODBC DSN 已設定（參見 `docs/01_architecture/ClickHouse_ODBC_Setup.md`）
- Python 3.10+

### 6.2 步驟一覽

```text
Step 1 → setup_schema.py      建立所有 DB / Table / View
Step 2 → sync_unified_odbc.py 從 MSSQL 拉取 Bronze 資料
Step 3 → execute_etl.py       Silver + Gold 全量回補
Step 4 → Cube.js 啟動         語義層上線
```

### 6.3 執行指令

```powershell
# Step 1: Schema 初始化（冪等，可安全重跑）
python scripts/etl/setup_schema.py

# Step 2: Bronze 全量同步
python scripts/etl/sync_unified_odbc.py --table all

# Step 3: Silver + Gold 歷史回補
python scripts/etl/execute_etl.py --backfill --start 2025-01-01 --step-days 10 --low-ram

# Step 4: Cube.js 啟動
cd cube
npm install
npm run dev
```

> **注意**：Step 3 的 `--start` 日期應設為需要的最早資料日期。`--low-ram` 啟用記憶體保護模式，建議在 Server 76 環境下必須使用。

### 6.4 驗證

執行完成後，可透過以下方式驗證：
1. 確認 `bronze._sync_watermark` 有所有 18 張表的記錄
2. 確認 `ops_metrics.etl_checkpoint` 所有 step 為 `SUCCESS`
3. 查詢 `gold.rmv_l5_task_completion_phys` 確認 Bitmap KPI 資料產出
4. 查詢 `gold.rmv_l5_task_summary` 確認預聚合整數資料產出（Cube.js 查詢入口）

---

**版本號**：v5.2.0 (合併 From-Scratch 部署指南)  
**更新日期**：2026-04-23  
**相關文件**：
- 架構總覽：`docs/01_architecture/Architecture_Overview.md`
- ETL 轉換管線：`docs/03_metrics/02_ETL_Transformation_Pipeline.md`
- ODBC 設定：`docs/01_architecture/ClickHouse_ODBC_Setup.md`
