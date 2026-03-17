# DMP Flowable 流程分析系統 (DMP Flowable Process Analytics)

本專案是一套基於 **Flowable BPM** 的自動化資料流與數據分析系統。其核心目標在於將分散的 BPM 流程數據透過 ETL Pipeline 整合至高效能數據倉儲，產出量化的生產管理指標。

## 1. 專案背景 (Project Background)

*   **系統目的**：分析 Flowable BPM 的流程執行效率，協助管理人員掌握生產瓶頸。
*   **數據來源**：MSSQL 伺服器 (包含 `APP_SRV_BPM` 核心流程表與 `APP_SRV_COMMON` 員工/製造維度主檔)。
*   **核心指標**：
    *   **L5 (任務完成率)**：精確計算 Todo (待辦)、Doing (執行中)、Done (已完成) 狀態與 Acc (累積在途量)。
    *   **L7 (人員使用率)**：分析系統活躍用戶與配置用戶的比率。
    *   **ISO 週次合規**：實作 Dn-1 動態日期邏輯，確保跨年份與週次的數據統計符合製造業規範。

---

## 2. 系統架構與資料流水線 (System Architecture & Pipeline)

本系統採用現代化數據倉儲架構，將數據分為 Bronze、Silver、Gold 三層進行轉化。

### 系統架構圖 (Architecture Overview)

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        MSSQL 來源系統                                │
│  ┌────────────────────────────┐  ┌────────────────────────────────┐ │
│  │ APP_SRV_BPM               │  │ APP_SRV_COMMON                 │ │
│  │ • ACT_HI_TASKINST_0108    │  │ • HR_Employee_0202             │ │
│  │ • ACT_HI_VARINST_0108     │  │ • MDM_*_0202 (主檔)            │ │
│  │ • ACT_HI_PROCINST_0108    │  │                                │ │
│  └────────────────────────────┘  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ Python 同步腳本 (增量/全量)
┌─────────────────────────────────────────────────────────────────────┐
│  Bronze 層 (原始資料)           ClickHouse Server                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ • bpm_act_hi_taskinst  (任務實例，增量同步)                     ││
│  │ • bpm_act_hi_varinst   (流程變數，增量同步)                     ││
│  │ • common_hr_employee   (員工，全量同步)                         ││
│  │ • common_mdm_*         (MDM 主檔，全量同步)                     ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ Materialized View (Bronze INSERT 觸發)
┌─────────────────────────────────────────────────────────────────────┐
│  Silver 層 (清洗轉換)                                               │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Layer 1:                                                        ││
│  │ • mv_varinst_pivoted      (每日凌晨 02:00 自動刷新)              ││
│  │ • mv_dim_mfg_five_level   (五階維度，MDM 整合版)                ││
│  │                                                                 ││
│  │ Layer 2:                                                        ││
│  │ • mv_fact_task_vx         (核心事實表，含 Vx 歸屬邏輯)          ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ 階層式錯開刷新 (04:00~05:00 AM)
┌─────────────────────────────────────────────────────────────────────┐
│  Gold 層 (指標快照)                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ • rmv_l5_task_completion  (L5 任務完成率，每日 04:00 自動刷新)   ││
│  │ • rmv_user_utilization    (人員使用率，每日 05:00 自動刷新)      ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  應用層                                                             │
│  • Cube.js 語意層 API (Superset 介接)                               │
│  • FastAPI L5 Insight API (自定義進階報表)                          │
│  • Apache Superset 視覺化面板                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 資料更新時序 (Data Update Process)

```text
時間軸 (T0 -> T4):
├─ T0: Bronze 同步完成 (Python 腳本執行增量/全量同步)
│
├─ T1: Silver Layer 1 異步刷新 (mv_varinst_pivoted 與 mv_dim_mfg_five_level)
│
├─ T2: Silver Layer 2 自動更新 (mv_fact_task_vx 觸發更新)
│
├─ T3: Gold 層刷新 (每日凌晨 04:00~05:00 自動啟動)
│
└─ T4: 應用層查詢可用 (上班前完成更新，數據即時準確)
```

---

## 3. 快速上手 (Quick Start)

### 1. 環境準備
請確保已安裝 Python 3.9+，並安裝必要的依賴套件。
```powershell
pip install -r requirements.txt
```

### 2. 初始化與 DB 重建 (Database Init)
若需在新機器建立所有資料表結構與物化視圖：
```powershell
# 此腳本會依序執行 sql/etl/ 下的所有 DDL 與 MView 定義
python scripts/etl/execute_etl.py
```

### 3. 環境變數設定 (Environment)
請參考 `infra/` 目錄下的 `.env` 設定，並依據 `infra/README.md` 的指示填入 MSSQL 與 ClickHouse 的連線資訊。

### 4. 執行資料同步 (Run Sync)
執行 ETL 作業，將數據從 MSSQL 拉取至 ClickHouse：
```powershell
# 執行 Unified Sync (支援增量同步流程與全量同步維度)
python scripts/etl/sync_unified.py
```

---

## 4. 核心文件索引 (Core Documents)

| 文件名稱 | 說明 |
| :--- | :--- |
| **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** | **[目錄]** 專案完整目錄結構與各檔案用途索引。 |
| **[docs/00_INDEX.md](docs/00_INDEX.md)** | **[索引]** 所有技術文件的分類導覽入口。 |
| **[docs/01_architecture/01_Architecture_Overview.md](docs/01_architecture/01_Architecture_Overview.md)** | **[架構]** 系統架構總覽、Bronze/Silver/Gold 資料流轉說明。 |
| **[docs/02_deployment/02_Deployment_Guide.md](docs/02_deployment/02_Deployment_Guide.md)** | **[部署]** Docker 部署、JDBC 設定、資料初始化與故障排除指南。 |
| **[docs/03_metrics/03_Metrics_and_Data_Definitions.md](docs/03_metrics/03_Metrics_and_Data_Definitions.md)** | **[指標]** 業務指標 (L5/L7) 規格定義與五階維度血緣。 |
| **[docs/04_serving/API_DOCUMENTATION.md](docs/04_serving/API_DOCUMENTATION.md)** | **[API]** FastAPI L5 Insight API 介面規格與使用範例。 |
| **[scripts/etl/README.md](scripts/etl/README.md)** | **[維運]** ETL 腳本工具箱使用手冊 (`execute_etl.py` / `sync_unified.py`)。 |

---

## 5. 關鍵功能 (Key Features)

- **高效能 L5 滾動累積**：實作 `ARRAY JOIN` 優化，運算資源消耗降低 98%，避免 OOM 記憶體溢出。
- **多階層區域映射**：解決線別資料缺失問題，透過「線別 -> 廠區」兩段式關聯，將 `UNKNOWN` 區域數據減至 0。
- **自動化維度補齊**：整合 VARINST 與 MDM 來源，自動映射製造五階組織維度。
- **離峰階層式刷新**：每日凌晨 02:00 ~ 05:00 依序串接刷新，確保數據依賴與系統穩定。

---

## 6. 專案結構 (Project Structure)

```
dmp_flowable/
├── api/                        # FastAPI L5 Insight API 實作
├── cube/                       # Cube.js 語意層定義
├── docs/                       # 系統化技術文件
│   ├── 01_architecture/        # 架構圖與系統流轉
│   ├── 02_deployment/          # 部署與維護手冊
│   ├── 03_metrics/             # 指標定義與資料映射
│   ├── 04_serving/             # 應用服務層 (API & Superset)
│   ├── 05_monitoring/          # 效能壓測與監控
│   └── 06_reports/             # 數據差異稽核報告
├── infra/                      # 基礎設施 (ClickHouse, API, Monitoring 堆疊)
├── scripts/                    # Python 腳本 (ETL, Validation, Debug)
├── sql/                        # Bronze → Silver → Gold 轉換邏輯
└── README.md                   # 專案入口文件
```

