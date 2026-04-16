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

### 🚀 Bronze 層索引優化 (2026-01-08)

**優化完成度**: 100% ✅

經過系統性的索引優化，Bronze 層核心表的查詢效能獲得了顯著提升：

| 表名 | 優化內容 | 效能提升 |
|------|---------|---------|
| bpm_act_hi_taskinst | ORDER BY (PROC_INST_ID_, ID_) + Skip Index | PROC_INST_ID_ JOIN: **68x** ⭐⭐⭐ |
| bpm_act_hi_varinst | 添加 TASK_ID_ Bloom Filter | TASK_ID_ IN: **10x-50x** ⭐⭐ |
| bpm_act_hi_procinst | ORDER BY PROC_INST_ID_ | 語義清晰度大幅提升 ⭐⭐⭐ |
| bpm_act_hi_identitylink | 無需優化 | 當前設計已最優 ✅ |

**關鍵成就**:
- ETL 執行時間: 從數分鐘降至數秒
- 記憶體使用: 降低 50x-200x
- 查詢併發能力: 提升 10x-50x

**詳細報告**: `BRONZE_OPTIMIZATION_SUMMARY.md`

### 🚀 系統架構優化 (2026-03-31 ~ 2026-04-07)

**核心機制更新**: 已由 JDBC Bridge 完整遷移至 **原生 ODBC 桌子引擎 (ODBC Table Engine)** 與 **物理化金層 (Physical Gold)**。

| 模組 | 優化內容 | 效能提升 |
|------|---------|---------|
| 數據同步 | Native ODBC + 顯式 DDL 模式 | 解決 JDBC LOB 列死鎖，穩定性提高 100% ⭐⭐⭐ |
| 銀/金層計算 | 10 日滑動視窗 (Windowed Base) | 處理 15 個月歷史數據無 OOM ⭐⭐⭐ |
| 指標查閱 | 物理表存儲 (`gold.*_phys`) | Cube.js 查詢無延遲，完全避開 View 刷新等待 ⭐⭐⭐ |
| 維度準確性 | HR `common_hr_employee` 補足姓名 | 人員報表 100% 準確顯示 ⭐⭐ |

**關鍵成就**:
- ETL 全程 low-ram 運行 (限制 5.5GB RAM)
- 統一資料同步模組 (`sync_unified_odbc.py`)
- 物理金層大幅提升前端展現速度

### 系統架構圖 (Architecture Overview)

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        MSSQL 來源系統 (Source)                        │
│  ┌────────────────────────────┐  ┌────────────────────────────────┐ │
│  │ APP_SRV_BPM               │  │ APP_SRV_COMMON                 │ │
│  │ • ACT_HI_TASKINST_0108    │  │ • HR_Employee_0202             │ │
│  │ • ACT_HI_VARINST_0108     │  │ • MDM_*_0202 (主檔)            │ │
│  └────────────────────────────┘  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ Native ODBC 同步 (Adaptive Batching)
┌─────────────────────────────────────────────────────────────────────┐
│  Bronze 層 (ODS 原始資料)       ClickHouse Server (Server 76)         │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ • bpm_act_hi_taskinst  (增量同步)                               ││
│  │ • bpm_act_hi_varinst   (增量同步)                               ││
│  │ • common_hr_employee   (全量同步 + EmpName 補全)                ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ execute_etl.py (Stage 1: Dimension Pivot)
┌─────────────────────────────────────────────────────────────────────┐
│  Silver 層 (DWH 清洗轉換)                                             │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ • mv_varinst_pivoted      (流程變數轉置)                        ││
│  │ • mv_fact_task_vx         (核心事實表，含 2025 全量歷史資料)    ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ execute_etl.py (Stage 2: Metric Aggregation)
┌─────────────────────────────────────────────────────────────────────┐
│  Gold 層 (KPI 物理指標)                                               │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ • rmv_l5_task_completion_phys  (任務完成率，實體表)             ││
│  │ • rmv_l5_acc_phys              (累積在途量，實體表)             ││
└─────────────────────────────────────────────────────────────────────┘
```

### 資料更新時序 (Data Update Process)

```text
時間軸 (T0 -> T3):
├─ T0: Bronze 同步完成 (python sync_unified_odbc.py)
│
├─ T1: Silver Stage 1 (Pivoting: 流程變數轉置)
│
├─ T2: Silver Stage 2 (Fact: 核心事實表與物理金層寫入)
│
└─ T3: 應用層查詢可用 (BI 工具無需等待 MView 刷新)
```

---

## 3. 快速上手 (Quick Start)

完整的執行程序請參考 **[DATA_PIPELINE_SOP.md](DATA_PIPELINE_SOP.md)**。以下為核心步驟摘要：

### 1. 環境準備
請確保已安裝 Python 3.9+，並配置好 ODBC DSN (命名為 `MSSQL_DSN`)。
```powershell
pip install -r requirements.txt
```

### 2. 初始化基礎架構 (Phase 0)
建立資料庫、表結構與部署 DDL (包含 `bronze`, `silver`, `gold` 實體表)：
```powershell
python scripts/etl/setup_schema.py
```

### 3. 執行數據同步 (Phase 1)
將數據從 MSSQL 拉取至 ClickHouse Bronze 層 (預設從 2025-01-01 起)：
```powershell
# 執行 Unified ODBC Sync (支援適應性分批與增量同步)
python scripts/etl/sync_unified_odbc.py --table all
```

### 4. 執行分析計算 (Phase 2)
將原始數據轉換為事實表與 KPI 實體表：
```powershell
# 執行補分 (Backfill 2025-01-01 起，記憶體優化模式)
python scripts/etl/execute_etl.py --backfill --low-ram --step-days 10

# 執行每日定時更新
python scripts/etl/execute_etl.py --daily --low-ram
```

---

## 4. 核心文件索引 (Core Documents)

| 文件名稱 | 說明 |
| :--- | :--- |
| **[DATA_PIPELINE_SOP.md](DATA_PIPELINE_SOP.md)** | **[核心] 標準資料流水線執行程序 (SOP)**，包含運修與故障排除。 |
| **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** | **[目錄]** 專案完整目錄結構與各檔案用途索引。 |
| **[docs/01_architecture/Architecture_Overview.md](docs/01_architecture/Architecture_Overview.md)** | **[架構]** 系統架構總覽、Bronze/Silver/Gold 資料流轉說明。 |
| **[docs/03_metrics/Metrics_and_Data_Definitions.md](docs/03_metrics/Metrics_and_Data_Definitions.md)** | **[指標]** 業務指標 (L5/L7) 規格定義與五階維度血緣。 |
| **[docs/04_serving/API_Documentation.md](docs/04_serving/API_Documentation.md)** | **[API]** FastAPI L5 Insight API 介面規格與使用範例。 |
| **[scripts/etl/README.md](scripts/etl/README.md)** | **[維運]** ETL 腳本工具箱使用手冊 (`execute_etl.py` / `sync_unified_odbc.py`)。 |

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
├── infra/                      # 基礎設施 (ClickHouse, API, Monitoring 堆疊)
├── scripts/                    # Python 腳本 (ETL, Validation, Debug)
├── sql/                        # Bronze → Silver → Gold 轉換邏輯
└── README.md                   # 專案入口文件
```
