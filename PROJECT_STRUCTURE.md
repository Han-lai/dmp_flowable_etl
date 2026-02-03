# 專案結構說明 (Project Structure)

**版本**: 2.1 (架構優化與 L5 對齊版)  
**更新日期**: 2026-02-03  
**重整狀態**: 已完成標準化與環境大掃除

---

## 📁 標準化專案結構

```
dmp_flowable/
├── claude.md                    # 🚀 快速上手與開發指南 (New)
├── PROJECT_STRUCTURE.md        # 本檔案 ⭐
├── memory-bank/                # 🧠 核心記憶庫 (activeContext, progress, etc.)
├── README.md                    # 專案總覽
├── GETTING_STARTED.md          # 新人快速開始指南
├── ARCHITECTURE.md             # 系統架構說明
├── REBUILD_GUIDE.md            # 完整重建指南
│
├── config/                     # 設定檔 ⭐
│   ├── environments/          # 環境變數 (development.env.example)
│   ├── clickhouse/           # ClickHouse 設定
│   ├── jdbc-bridge/          # JDBC Bridge 設定
│   └── cube-js/              # Cube.js 設定
│
├── docs/                       # 📄 核心技術文檔 (已依序編號) ⭐
│   ├── 00_INDEX.md             # 文檔總目錄
│   ├── 01_Architecture_Overview.md
│   ├── 01b_System_Flow_Diagram.md
│   ├── 02_E2E_Implementation_Guide.md # 核心開發手冊
│   ├── 03_Business_Metric_Definitions.md # 業務指標定義
│   ├── 04_Data_Lineage_Mapping.md
│   ├── 05_Field_Verification_Reference.md
│   ├── 06_Technical_Deep_Dive_MViews.md
│   ├── guides/                 # 操作指南 (superset_dashboard_guide.md)
│   ├── specs/                  # 指標技術規格書 (L5, L7)
│   └── archive/                # 歷史檔案、調查報告與舊版映射
│
├── sql/                        # 🏛️ 資料庫定義 (Source of Truth) ⭐
│   └── rebuild/                # v2.1 穩定版重建 SQL (01, 03, 04, 06...)
│
├── scripts/                    # 🐍 執行腳本 (已清理冗餘腳本) ⭐
│   ├── rebuild/                # 重建與同步任務 (sync_unified.py, execute_rebuild.py)
│   ├── validation/             # 正式驗證工具 (multi_scenario_verify.py, quick_stats.py)
│   └── sync/                   # 基礎同步腳本 (sync_incremental.py)
│
├── cube/                       # 🧊 Cube.js 語意層
│   ├── model/cubes/           # 指標語意定義
│   └── docker-compose.yml     # 服務編排
│
├── docker/                     # 🐋 基礎設施 (Docker Compose)
│   ├── clickhouse/
│   └── jdbc-bridge/
│
└── ARCHIVE/                    # 🗃️ 專案歷史歸檔
    ├── misc/CLAUDE.md          # 2026-01-30 舊版進度紀錄
    ├── scripts_old/
    └── sql_old/
```

---

## 🎯 核心檔案說明 (Updated)

### 📋 入口引導
- **`claude.md`** - **開發首選入口**，包含當前狀態、常用指令與 L5 結案進度。
- **`PROJECT_STRUCTURE.md`** - 本檔案，定義專案各目錄之用途。
- **`GETTING_STARTED.md`** - 提供一鍵部署與基礎環境建立流程。

### 🐍 腳本分類 (精簡版)
我們在 v2.1 中移除約 100 份一次性腳本，僅保留核心工具：
- **`scripts/rebuild/`**: 包含數據同步、SQL 批次執行與系統重建。
- **`scripts/validation/`**: 包含三方比對、單場景對帳與快速統計。

### 🏛️ SQL 核心管線
- **`sql/rebuild/`**: 定義了從 Bronze 到 Gold 的完整資料轉換路徑。
  - `03_silver_pivot`: 採用 **Refreshable MView** 的關鍵組件。
  - `04_silver_fact`: 支援多時間點的任務事實表。

### � 文件編號系統
文檔目錄 `docs/` 採用 **01~06 序號命名**，確保開發人員能按邏輯順序讀取系統架構與業務邏輯。

---

## 🔄 相容性說明
雖然我們清理了目錄，但核心同步指令（如 `sync_incremental.py`）與數據庫路徑（`sql/rebuild/`）保持不變，並與 `deploy.py` 腳本兼容。

---
**最後更新**: 2026-02-03  
**版本**: 2.1 (Restored Detailed Layout)