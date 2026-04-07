# ETL 工具集 (scripts/etl) - ODBC 穩定版

此目錄包含 DMP Flowable 數據流水線（Data Pipeline）的核心執行工具。目前已全面遷移至 **原生 ODBC 同步架構**，徹底解決了舊版 JDBC Bridge 的穩定性與記憶體問題。

## 💡 資料流架構 (Architecture)

1.  **數據抽取 (Phase 1)**: 使用 `sync_unified_odbc.py` 透過 `ENGINE = ODBC` 直接從 MSSQL 抓取數據至 ClickHouse **Bronze 層**。
2.  **數據轉換 (Phase 2)**: 使用 `execute_etl.py` 分兩階段進行分析計算：
    *   **Stage 1**: 執行流程變數的轉置（Dimension Pivot）。
    *   **Stage 2**: 執行核心事實表（Fact Tasks）與金層指標（Gold KPI）的物理化存儲。

---

## 🛠️ 核心工具說明

### 1. `setup_schema.py` - 基礎架構初始化
在首次部署或 Schema 變更時執行。它會根據 `config/infra_config.yaml` 的定義，自動建立資料庫與所有必要的資料表結構。
*   **用法**: `python setup_schema.py`
*   **參數**: `--force` (強制重建所有表，會刪除現有數據，請謹慎使用)。

### 2. `sync_unified_odbc.py` - 統一數據同步引擎
取代了舊有的 `sync_unified.py`，專為 Server 76 的低記憶體環境設計。
*   **特性**:
    *   **適應性分切 (Adaptive Splitting)**: 當遇到大表同步 OOM 時，會自動將時間視窗切細後重試。
    *   **顯式 DDL 模式**: 透過手動定義欄位類型，避免 ODBC 驅動在探測 Metadata 時造成 MSSQL 鎖表。
    *   **1:1 對齊**: 對於 MDM/HR 等主檔，採用 `TRUNCATE + INSERT` 策略確保資料與來源端完全一致。
*   **用法**: `python sync_unified_odbc.py --table all`
*   **常用參數**: `--start YYYY-MM-DD`, `--step-days 10`。

### 3. `execute_etl.py` - 兩階段分析運算引擎
負責執行 Silver 與 Gold 層的 SQL 邏輯。
*   **分段運算**: 支援 `--step-days` 參數，將長時間範圍的計算切分為小視窗，確保在 6GB RAM 下也能處理千萬級數據。
*   **物理金層 (Physical Gold)**: 不同於舊版的 View，現在會將 KPI 指標直接重寫入物理表 (`_phys`)，大幅提升 BI (Cube.js/Superset) 的查詢效能。
*   **用法**: `python execute_etl.py --daily --low-ram` (日常增量更新)。

---

### 4. `optimize_tables.py` - 資料唯一性維護工具 (NEW)
針對 `ReplacingMergeTree` 引擎的自動維護工具。
*   **功能**: 批次對所有 Bronze/Silver/Gold 表執行 `OPTIMIZE TABLE ... FINAL`。
*   **目的**: 強制 ClickHouse 合併背景分片，移除因多次同步產生的重複記錄。

---

## 📋 同步策略清單 (Sync Matrix)

| 表名關鍵字 | 策略 | 說明 |
| :--- | :--- | :--- |
| `taskinst`, `varinst` | **batch** | 以時間視窗進行增量同步 (預設 10 日)。 |
| `hr_employee`, `mdm_*` | **full** | 每日全量覆蓋，確保維度資料 100% 準確。 |
| `procdef`, `user_group` | **full** | 小表全量更新。 |

---

## 🔧 維運事項 (Internal Maintenance)

*   **密碼管理**: ClickHouse 連線資訊統一在腳本頂部的 `CH_CONFIG` 或環境變數中設定。
*   **Watermark 重置**: 若需重跑特定表的同步，請刪除 `bronze._sync_watermark` 中的對應紀錄。
*   **欄位變更**: 若 MSSQL 來源端異動欄位，請同步修改 `config/sync_tables.yaml` 並重新執行 `setup_schema.py`。
