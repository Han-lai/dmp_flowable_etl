# 實作手冊 2：ETL 數據同步引擎與 Watermark 維運手冊

本手冊詳述 `sync_unified.py` 腳本的核心運作機制，包含自動增量同步、Watermark 控制與異常重試邏輯。

---

## 1. 核心同步引擎：`sync_unified.py`
這是整套系統的數據搬運大腦，支援「全量」與「增量批次」兩大策略。

### **1.1 資料表同步配置 (`TABLE_CONFIGS`)**
開發者可在字典中定義新表，腳本會自動處理：
```python
TABLE_CONFIGS = {
    # 增量批次同步範例 (大表)
    "taskinst": {
        "source": "APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108",
        "target": "bronze.bpm_act_hi_taskinst",
        "time_col": "START_TIME_", # 用於增量判斷的欄位
        "strategy": "batch",
        "columns": "*"
    },
    # 全量覆蓋同步範例 (配置表)
    "procdef": {
        "source": "APP_SRV_BPM.dbo.ACT_RE_PROCDEF_0108",
        "target": "bronze.bpm_act_re_procdef",
        "strategy": "full",
        "columns": "*"
    }
}
```

---

## 2. 增量控制：Watermark 機制
系統不依賴外部狀態存儲，而是直接在 ClickHouse 建立一個小表來記錄同步進度。

### **2.1 Watermark 表結構**
```sql
CREATE TABLE IF NOT EXISTS bronze._sync_watermark (
    table_name String,
    last_sync_time DateTime64(3), -- 最後成功同步到的數據時間點
    sync_time DateTime64(3),      -- 執行同步的系統時間
    row_count UInt64              -- 該批次同步的行數
) ENGINE = ReplacingMergeTree(sync_time)
ORDER BY (table_name)
```

### **2.2 增量過濾 SQL**
在 `sync_batch` 函式中，系統會動態生成帶有時間區間的 JDBC 查詢：
```python
insert_sql = f"""
INSERT INTO {target}
SELECT *, now64(3) as _extracted_at
FROM jdbc('{JDBC_DATASOURCE_NAME}', '
    SELECT {cols} FROM {source}
    WHERE {time_col} >= ''{start_str}'' AND {time_col} < ''{end_str}''
')
"""
```

---

## 3. 維運操作建議
當同步出現問題時，維護人員可透過以下指令進行操作：

### **3.1 手動觸發特定表同步**
```powershell
python scripts/etl/sync_unified.py --table taskinst --start "2024-01-01"
```

### **3.2 重設同步起點 (Backfill)**
若需重啟之前的數據，只需手動刪除 Watermark 紀錄：
```sql
ALTER TABLE bronze._sync_watermark DELETE WHERE table_name = 'bronze.bpm_act_hi_taskinst'
```

---
> [!TIP]
> **自動分片重試**：若 MSSQL 因查詢範圍過大而逾時，腳本具備 `sync_batch_adaptive` 邏輯，會自動將時間區間減半並重試，直到成功為止。

---
**文件維護資訊**
*   **版本號**：v1.0.0
*   **更新日期**：2026-03-12
*   **維護人員**：albee
