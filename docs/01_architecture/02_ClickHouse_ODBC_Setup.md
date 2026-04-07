# ClickHouse ODBC 資料同步配置 (ODBC Data Sync Setup)

本文件說明如何配置 ClickHouse 與 MSSQL 之間的原生 ODBC 同步機制。此機制取代了舊有的 JDBC Bridge，提供更高的穩定性與效能。

## 1. ODBC DSN 配置 (DSN Configuration)

系統預期在作業系統層級配置一個名為 `MSSQL_DSN` 的資料來源。

*   **DSN 名稱**: `MSSQL_DSN`
*   **驅動程式**: `ODBC Driver 17 for SQL Server` (或更新版本)
*   **連線參數**:
    *   `Server`: [MSSQL 伺服器位址]
    *   `Database`: `APP_SRV_BPM` (預設)
    *   `MARS_Connection`: `yes` (建議開啟以支援多重活動結果集)

## 2. ClickHouse 原生 ODBC 引擎 (ODBC Table Engine)

同步腳本 `sync_unified_odbc.py` 採用「顯式 schema 代碼注入」模式，直接在 ClickHouse 中建立臨時的 ODBC 引擎表，繞過動態欄位偵測，避免 LOB 欄位造成的死鎖。

### 核心 DDL 範例:
```sql
CREATE TABLE odbc_temp_taskinst (
    ID_ String,
    PROC_INST_ID_ String,
    TASK_DEF_KEY_ String,
    NAME_ String,
    START_TIME_ DateTime64(3)
    -- ... 其他顯式定義的欄位
) ENGINE = ODBC('DSN=MSSQL_DSN;Database=APP_SRV_BPM;Uid=...;Pwd=...', 'dbo', 'ACT_HI_TASKINST_0108');
```

## 3. 同步工具 (`sync_unified_odbc.py`)

該腳本負責驅動數據流向 Bronze 層。

### 主要功能:
- **適應性分批 (Adaptive Batching)**: 若同步過程中發生超時或記憶體溢出，腳本會自動將時間區間減半並重試，直到成功為止。
- **水位線管理 (Watermarking)**: 紀錄每張表的 `last_sync_time` 於 `bronze._sync_watermark` 表中，支援增量續傳。
- **全量同步 (Full Sync)**: 對於維度主檔，使用 `TRUNCATE` + `INSERT` 確保資料 1:1 對齊。

## 4. 運維指令 (Operation Commands)

### 執行全量/增量同步:
```powershell
# 同步所有配置的資料表
python scripts/etl/sync_unified_odbc.py --table all

# 僅同步特定資料表 (如 HR 員工)
python scripts/etl/sync_unified_odbc.py --table common_hr_employee
```

### 檢查水位線:
```sql
SELECT * FROM bronze._sync_watermark FINAL;
```

---
**備註**: 本架構完全移除對 `clickhouse-jdbc-bridge` 的依賴，直接利用 ClickHouse 內置的 `ODBC` 引擎進行高併發數據提取。
