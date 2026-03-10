# 專案結構說明 (Project Structure)

**版本**: 4.0 (基礎設施整合與大清查版)  
**更新日期**: 2026-03-10

---

## 專案結構

```
dmp_flowable/
│
├── README.md                        # 專案入口總覽 (架構、快速上手)
├── PROJECT_STRUCTURE.md             # 本檔案 (目錄地圖)
├── PROJECT_AUDIT_REPORT.md          # 專案最終審核報告 (含效能指標)
├── claude.md                        # AI 助手快速上手指南
├── .gitignore
├── package.json
│
├── api/                             # FastAPI L5 Insight API 實作
│   ├── main.py                      # API 核心邏輯
│   └── requirements.txt             # API 依賴清單
│
├── config/                          # 核心配置 (JDBC, Env 範本)
│
├── docs/                            # 系統化技術文件 (中心化手冊)
│   ├── 01_architecture/        # 系統架構、資料流程、技術深鑽
│   ├── 02_deployment/          # 部署手冊 (DEPLOY_GUIDE)、系統啟動
│   ├── 03_metrics/             # 指標定義、資料血緣、查帳基準
│   ├── 04_serving/             # 應用服務層 (API 開發者文件、Superset 指南)
│   ├── 05_monitoring/                # 效能壓測報告、Grafana 面板配置
│   └── 06_reports/                   # 數據差異稽核報告
│
├── infra/                           # 基礎設施堆疊 (Infra Center)
│   ├── .env                         # 通用環境變數
│   ├── clickhouse/                  # ClickHouse 堆疊 (含 jdbc-bridge 與 compose 配置)
│   ├── api/                         # FastAPI 獨立服務堆疊 (含 compose 配置)
│   └── monitoring/                  # 監控堆疊 (Prometheus + Grafana + cAdvisor)
│
├── sql/                             # 資料庫轉換邏輯 (Source of Truth)
│   ├── setup/                       # 初始化 DDL
│   └── etl/                         # 核心管線 (Bronze → Silver → Gold)
│
├── scripts/                         # Python 執行腳本
│   ├── etl/                         # 生產同步 (核心主力)
│   ├── setup/                       # 一次性初始化腳本
│   └── validation/                  # 多維度驗證腳本
│       └── debug/                   # 散落測試檔案、臨時紀錄回收箱
│
├── cube/                            # 語意層建模 (Cube.js)
├── logs/                            # 各階段執行紀錄
└── memory-bank/                     # AI 助手上下文記憶庫
```

---

## 核心模組描述

| 模組 | 實體路徑 | 用途與重要度 |
| :--- | :--- | :--- |
| **API 服務** | `api/` | 提供 L5 報表數據，支援 GET/POST 請求。 |
| **基礎設施** | `infra/` | 所有的 Docker 容器定義、網路與監控管理中心。 |
| **文件中心** | `docs/` | 按 Architecture 到 Reports 分類，供後續維運查閱。 |
| **數據管線** | `sql/etl/` | 定義三層資料轉換的業務與技術邏輯。 |
| **同步腳本** | `scripts/etl/` | 每日負責從生產 MSSQL 抽檔至 ClickHouse。 |

---

## 核心模組速覽

| 模組 | 路徑 | 用途 |
|------|------|------|
| Docker 部署 | `docker/` | ClickHouse + JDBC Bridge 基礎設施 |
| SQL 管線 | `sql/etl/` | Bronze → Silver → Gold 三層資料轉換 |
| 同步腳本 | `scripts/etl/` | 生產環境資料同步與重建 |
| Cube.js | `cube/` | 語意層模型，驅動 Superset 儀表板 |
| 環境設定 | `config/environments/` | 開發 / 正式環境參數 |
| 技術文檔 | `docs/` | 架構、指標定義、操作指南 |

---

## 目錄分類

###  生產必要 (~45 檔案)
`docker/`, `sql/`, `scripts/etl/`, `cube/`, `config/`, 核心文件

###  開發過程產物 (~86 檔案)
`scripts/validation/` 全部子目錄 — 驗證邏輯正確性的一次性腳本

###  日誌與紀錄 (~20 檔案)
`logs/` — 各階段的輸出與報告