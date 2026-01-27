# 新人快速開始指南

**版本**: 1.0  
**更新日期**: 2026-01-28  
**適用對象**: 新加入專案的開發者

---

## 🎯 專案概述

**DMP Flowable 流程分析系統** 是一個完整的資料管道，架構如下：

```
MSSQL → JDBC Bridge → ClickHouse → Cube.js → Superset
```

**核心功能**:
- L5 任務完成率分析
- VARINST 優先，MDM 補齊的維度邏輯
- ISO Week 時間合規性
- V1/V3 歸屬邏輯 (315% 工單規則)

---

## 📋 環境準備檢查清單

### 必要軟體
- [ ] **Docker** (版本 20.10+)
- [ ] **Docker Compose** (版本 2.0+)
- [ ] **Python** (版本 3.8+)
- [ ] **Node.js** (版本 16+)
- [ ] **Git**

### Python 套件
```bash
pip install clickhouse-connect pandas python-dotenv
```

### 網路存取
- [ ] 可存取 MSSQL Server: `twtpesqldv2.delta.corp:1433`
- [ ] 可存取 ClickHouse: `REDACTED_IP:8121`

---

## 🚀 快速部署 (5 分鐘)

### 步驟 1: 取得專案
```bash
git clone [repository_url]
cd dmp_flowable
```

### 步驟 2: 環境設定
```bash
# 複製環境設定檔
cp config/environments/development.env.example config/environments/development.env

# 編輯設定檔 (填入實際連線資訊)
notepad config/environments/development.env
```

### 步驟 3: 啟動基礎服務
```bash
# 啟動 ClickHouse 和 JDBC Bridge
cd docker
docker-compose up -d

# 檢查服務狀態
docker-compose ps
```

### 步驟 4: 初始化資料庫
```bash
# 執行 DDL 腳本 (按順序)
python scripts/setup/initialize_database.py

# 驗證安裝
python scripts/setup/verify_installation.py
```

### 步驟 5: 同步資料
```bash
# 執行初始資料同步
python scripts/sync/sync_initial_data.py

# 驗證資料
python scripts/validation/verify_data_integrity.py
```

### 步驟 6: 啟動 Cube.js
```bash
cd cube
docker-compose up -d

# 檢查 Cube.js 狀態
curl http://localhost:4000/cubejs-api/v1/meta
```

---

## 📁 專案結構說明

```
dmp_flowable/
├── README.md                    # 專案總覽
├── GETTING_STARTED.md          # 本檔案
├── REBUILD_GUIDE.md            # 完整重建指南
├── ARCHITECTURE.md             # 系統架構說明
│
├── config/                     # 設定檔
│   ├── environments/          # 環境變數
│   ├── clickhouse/           # ClickHouse 設定
│   └── jdbc-bridge/          # JDBC Bridge 設定
│
├── scripts/                   # 執行腳本
│   ├── setup/               # 安裝設定
│   ├── sync/                # 資料同步
│   ├── validation/          # 驗證測試
│   └── maintenance/         # 維護工具
│
├── sql/                      # SQL 檔案
│   ├── ddl/                 # 資料定義 (建表)
│   ├── dml/                 # 資料操作 (更新)
│   └── validation/          # 驗證查詢
│
├── cube/                     # Cube.js 語意層
│   └── model/cubes/         # 資料模型
│
├── docs/                     # 文件
│   ├── architecture/        # 架構文件
│   ├── user-guides/         # 使用指南
│   └── troubleshooting/     # 故障排除
│
├── logs/                     # 執行日誌
├── validation_results/       # 驗證結果
└── ARCHIVE/                  # 歷史檔案
```

---

## 🔧 常用指令

### 資料同步
```bash
# 全量同步
python scripts/sync/sync_full.py

# 增量同步
python scripts/sync/sync_incremental.py

# 同步特定表
python scripts/sync/sync_table.py --table bronze.bpm_act_hi_taskinst
```

### 驗證測試
```bash
# 資料完整性驗證
python scripts/validation/verify_data_integrity.py

# MSSQL vs ClickHouse 對帳
python scripts/validation/verify_reconciliation.py

# 端到端測試
python scripts/validation/test_end_to_end.py
```

### 維護工具
```bash
# 備份重要表
python scripts/maintenance/backup_tables.py

# 清理舊日誌
python scripts/maintenance/cleanup_logs.py

# 效能監控
python scripts/maintenance/monitor_performance.py
```

---

## 🚨 故障排除

### 常見問題

#### Q1: JDBC Bridge 連線失敗
```bash
# 檢查 JDBC Bridge 狀態
docker logs clickhouse-jdbc-bridge

# 測試連線
python scripts/setup/test_jdbc_connection.py
```

#### Q2: ClickHouse 連線失敗
```bash
# 檢查 ClickHouse 狀態
docker logs clickhouse-server

# 測試連線
python scripts/setup/test_clickhouse_connection.py
```

#### Q3: 資料同步失敗
```bash
# 檢查同步日誌
ls -la logs/sync_*

# 重新同步特定表
python scripts/sync/resync_table.py --table [table_name]
```

### 取得協助
1. 查看 `docs/troubleshooting/` 資料夾
2. 檢查 `logs/` 資料夾中的錯誤日誌
3. 聯繫專案維護者

---

## 📚 進階學習

### 必讀文件
1. `ARCHITECTURE.md` - 系統架構深度說明
2. `docs/user-guides/data-pipeline-guide.md` - 資料管道詳解
3. `docs/user-guides/cube-js-guide.md` - Cube.js 使用指南

### 開發指南
1. `docs/development/coding-standards.md` - 程式碼規範
2. `docs/development/testing-guide.md` - 測試指南
3. `docs/development/deployment-guide.md` - 部署指南

---

**🎉 恭喜！你已經完成基本設定，可以開始使用系統了！**

如有任何問題，請參考 `docs/troubleshooting/` 或聯繫專案團隊。