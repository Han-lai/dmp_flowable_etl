# ETL 腳本工具目錄 (`scripts/etl`)

此目錄包含負責從來源系統 (MSSQL) 抽取資料、清洗並轉換至 ClickHouse (Bronze, Silver, Gold) 的核心工具。

## 🚀 核心執行腳本 (Core Scripts)

本目錄已簡化為兩大主要 Python 工具，配合自動化腳本完成所有資料管線作業。

### 1. `execute_etl.py` - 結構建立、管理與狀態檢查
負責依序執行 `sql/etl/` 下的 SQL 檔案來建立各層級架構，並提供自動化與檢查功能。
- **基本用法**: `python execute_etl.py` (發現表存在時會互動式詢問是否重建)
- **安全模式**: `python execute_etl.py --skip-existing` (偵測到表已存在則自動跳過，適合僅更新 MView 或補建缺表)
- **強制模式**: `python execute_etl.py --force` (自動確認所有重建動作，會執行 DROP TABLE)
- **狀態檢查**: `python execute_etl.py --status` (整合原 `check_sync_status.py` 功能，查看同步進度與各表筆數)

### 2. `sync_unified.py` - 資料同步主體
負責從 MSSQL 抽取資料並灌入 ClickHouse Bronze 層。
- **全量同步**: `python sync_unified.py --table all` (同步所有定義在 `TABLE_CONFIGS` 中的表)
- **單表同步**: `python sync_unified.py --table <table_key>` (例如 `taskinst`)
- **增量同步**: 預設會讀取進度表 (Watermark)，自動從上次結束點繼續。

## 📂 自動化封裝 (Wrappers)

- **`init_pipeline.sh`**: **首次部署專用**。依序執行 `execute_etl.py` (建立結構) 與 `sync_unified.py --table all` (同步歷史資料)。
- **`daily_etl_wrapper.sh`**: **日常排程專用**。僅執行 `sync_unified.py` 進行增量更新。

---

## 🛠️ 維運建議 (Best Practices)

1. **修改計算邏輯 (SQL)**: 
   如果您修改了 Silver 或 Gold 層的 SQL，想重新計算報表但不影響原始資料，請執行：
   `python execute_etl.py --skip-existing`
   (它會跳過已存在的 Bronze 表，並在詢問到 Silver/Gold 時選 `y` 進行重建)。

2. **檢查資料是否準確**:
   執行 `python execute_etl.py --status` 觀察 `bronze._sync_watermark` 的時間戳記與各表 Rows 數量。
