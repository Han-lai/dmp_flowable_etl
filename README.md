# DMP Flowable 流程分析系統

基於 ClickHouse → Cube.js → Superset 的現代化資料管道，專注於 Flowable BPM 的流程效率分析 (L5/L7)。

> [!IMPORTANT]
> **本專案的核心文件與架構定義以 [PROJECT_AUDIT_REPORT.md](PROJECT_AUDIT_REPORT.md) 為單一真理來源 (Source of Truth)。**
> 所有架構圖、資料流、業務邏輯 (L5/V1/V3/ISO) 請優先參考該文件。

## 🚀 快速上手 (Quick Start)

### 1. 環境準備
請確保已安裝 Python 3.9+ 與必要的依賴套件。
```bash
pip install -r requirements.txt
```

### 2. 資料庫重建 (Rebuild Database)
若需從零建立 Bronze/Silver/Gold 層結構，請執行：
```bash
# 此腳本會依序執行 sql/etl/ 下的所有 SQL 檔案
python scripts/etl/execute_etl.py
```

### 3. 資料同步 (Data Sync)
執行 ETL 作業，將 MSSQL 資料同步至 ClickHouse：
```bash
# 執行 Unified Sync (包含 Batch 與 Full 模式)
python scripts/etl/sync_unified.py
```

### 4. 資料驗證 (Validation)
驗證 ClickHouse 數據與 MSSQL 來源的一致性：
```bash
# 快速統計檢查
python scripts/validation/data_explore/quick_stats.py
```

---

## 📚 核心文件索引

| 文件名稱 | 說明 |
| :--- | :--- |
| **[PROJECT_AUDIT_REPORT.md](PROJECT_AUDIT_REPORT.md)** | **[核心]** 專案全審核報告，包含架構圖、業務邏輯與 SQL 清單。 |
| **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** | **[目錄]** 專案目錄結構說明與檔案用途索引。 |
| **[docs/02_E2E_Implementation_Guide.md](docs/02_E2E_Implementation_Guide.md)** | **[新手]** 端到端建置指南，包含環境準備與部署流程。 |

---

## ✨ 關鍵功能 (Key Features)

- **L5 任務完成率**: 計算準確的 Todo/Doing/Done 狀態與累積在途量 (Acc)。
- **ISO 週次合規**: 實作 W-pattern 與 Dn-1 動態日期邏輯，確保跨年週次正確。
- **V1/V3 歸屬邏輯**: 優先採用工單號 (moNumber) 進行 Vx 歸屬判定，解決 315% 工單的歸類問題。
- **維度補齊**: 整合 Flowable 變數 (VARINST) 與 MDM 主檔，自動補齊製造五階維度。

## 📁 專案結構簡介

```
dmp_flowable/
├── PROJECT_AUDIT_REPORT.md     # 核心架構文件
├── config/environments/        # 環境設定 (dev/prod)
├── docker/                     # ClickHouse + JDBC Bridge 部署
├── sql/
│   ├── setup/                  # 初始化 SQL
│   └── etl/                # Bronze → Silver → Gold SQL
├── scripts/
│   ├── etl/                # 🔄 生產同步腳本
│   ├── setup/                  # 🔧 一次性設定
│   └── validation/             # 🔍 驗證腳本 (7 個子類)
├── cube/                       # Cube.js 語意層
├── docs/                       # 技術文檔 (01~06)
└── logs/                       # 輸出與日誌
```

詳細結構請參閱 `PROJECT_STRUCTURE.md`。