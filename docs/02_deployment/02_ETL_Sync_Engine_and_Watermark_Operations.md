# 實作手冊 2 (ODBC 版)：ETL 數據同步引擎與 Watermark 運維

本手冊詳述 `sync_unified_odbc.py` 腳本的核心運作機制，基於 **Native ODBC Table Engine** 實作 1:1 的 MSSQL 數據同步。

---

## 1. 核心同步引擎：`sync_unified_odbc.py`
這是目前的數據搬運大腦，支援「全量」與「增量批次」兩大策略，並針對 Server 76 的記憶體限制進行了適應性調整。

### **1.1 資料表同步配置 (`TABLE_CONFIGS`)**
配置位於同目錄下 `config/sync_tables.yaml`。

### **1.2 顯式 DDL 機制**
腳本在同步時會動態建立臨時的 ODBC Engine 表，並注入顯式的 DDL schema，以避開自動偵測造成的大型欄位死鎖。

---

## 2. 增量控制：Watermark 機制
系統不依賴外部狀態，而是直接在 ClickHouse 建立 `bronze._sync_watermark` 表。

### **2.1 增量過濾邏輯**
在 `sync_batch` 腳本中，系統會動態生成 SQL 並透過 ODBC Engine 執行：
```sql
INSERT INTO {target}
SELECT {cols}, now() as _extracted_at
FROM odbc_temp_engine
WHERE {time_col} >= '{start_str}' AND {time_col} < '{end_str}'
```

---

## 3. 維運操作建議

### **3.1 手動觸發特定表同步**
```powershell
python scripts/etl/sync_unified_odbc.py --table taskinst --start "2025-01-01"
```

### **3.2 適應性分批 (Adaptive Batching)**
若發生 OOM 或超時，腳本會自動將時間區間減半重試。若需調整重試深度，請查閱代碼中的 `sync_batch_adaptive` 邏輯。

---
**版本號**：v5.0.0 (ODBC 版)
**更新日期**：2026-04-07
**備註**：Legacy JDBC 運作手冊請見 `02_ETL_Sync_Engine_and_Watermark_Operations.md`。
