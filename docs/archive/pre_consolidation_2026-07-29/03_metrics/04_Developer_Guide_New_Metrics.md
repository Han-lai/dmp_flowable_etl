# DMP Flowable：新指標開發作業指引 (Developer Guide)

本文件旨在指導開發者如何在 DMP Flowable 架構中新增一個業務指標（Metric）。整個過程遵循「銅 -> 銀 -> 金」三層資料演進模型。

## 核心流程總覽

```mermaid
graph LR
    A[Bronze: 原始接入] --> B[Silver: 清洗與事實]
    B --> C[Gold: 業務指標聚合]
    C --> D[Serving: Cube.js 語義層]
```

---

## 步驟一：銅層 (Bronze) - 原始資料接入

目的：將源頭 MS SQL 的資料安全、穩定地同步到 ClickHouse。

1.  **設定同步參數**：
    *   修改 [sync_tables.yaml](file:///d:/kiro/dmp_flowable/scripts/etl/config/sync_tables.yaml)。
    *   定義 `source` (MS SQL 表名)、`target` (Clickhouse 表名) 與 `engine_ddl`。
2.  **建立實體表 (DDL)**：
    *   修改 [01_bronze_flowable_core.sql](file:///d:/kiro/dmp_flowable/sql/etl/schema/01_bronze_flowable_core.sql)。
    *   **必須配置**：`PARTITION BY toYYYYMM(時間欄位)` 與 `TTL ... + INTERVAL 1 YEAR`。
3.  **執行首次同步**：
    ```powershell
    python scripts/etl/sync_unified_odbc.py --table <你的表名> --start 2025-01-01
    ```

---

## 步驟二：銀層 (Silver) - 資料清洗與事實化

目的：進行 EAV 轉置 (Pivoting)、多表關聯 (Join) 與資料標準化。

1.  **建立轉換邏輯 (DML)**：
    *   在 `sql/etl/dml/` 目錄下建立新的 `backfill_xxx_silver.sql`。
    *   > [!IMPORTANT]
        > 語法內必須使用 `{start_ts}` 與 `{end_ts}` 佔位符，以便 `execute_etl.py` 進行動態時間切片運算，防止 OOM。
2.  **定義事實表結構 (DDL)**：
    *   在 [04_silver_fact_tasks.sql](file:///d:/kiro/dmp_flowable/sql/etl/schema/04_silver_fact_tasks.sql) 中建立 `ReplacingMergeTree` 實體表。

---

## 步驟三：金層 (Gold) - 業務指標聚合

目的：根據業務邏輯計算最終指標，並持久化以供前端快速查詢。

1.  **建立聚合邏輯 (DML)**：
    *   在 `sql/etl/dml/` 建立指標聚合腳本 (例如 `backfill_gold_kpi.sql`)。
2.  **定義金層實體表 (DDL)**：
    *   在 [06_gold_kpi_task_completion.sql](file:///d:/kiro/dmp_flowable/sql/etl/schema/06_gold_kpi_task_completion.sql) 中建立存儲結果的物理表。

---

## 步驟四：自動化整合 (Orchestration)

目的：將新指標加入自動化流水線，確保每日更新。

1.  **更新 Pipeline 配置**：
    *   修改 [pipeline_config.yaml](file:///d:/kiro/dmp_flowable/scripts/etl/config/pipeline_config.yaml)。
    *   在 `pipeline_stages` 中新增一個 `step`，將剛才寫好的 SQL Template 對映到目標實體表。
2.  **全量回填測試 (Backfill)**：
    ```powershell
    # 建議加上 --low-ram 參數測試記憶體壓力
    python scripts/etl/execute_etl.py --backfill --start 2025-01-01 --low-ram
    ```

---

## 步驟五：服務層宣告 (Cube.js)

目的：將 ClickHouse 的實體表對映為語義化指標。

1.  **建立數據模型**：在 `cube/` 目錄下定義 `cube.js` 檔案。
2.  **定義 Measure/Dimension**：例如定義一個 `count` 類型的 Measure 作為該指標的數值。

---

## 開發者常見 Q&A

**Q：如果我只是要在現有報表多加一個欄位？**
1. 修改 `sync_tables.yaml` 與 Bronze DDL。
2. 修改對應的 Silver/Gold DML SQL 範本。
3. 執行 `execute_etl.py --backfill --reset` (注意：`--reset` 會清除舊資料重新計算，請謹慎使用)。

**Q：如何確保新增的 SQL 不會把伺服器跑爆？**
所有的長期運算務必使用 `execute_etl.py` 來執行，它會自動將時間範圍切細（如每 10 天一個窗口），若發生記憶體溢出 (OOM) 會自動將窗口減半重新嘗試。
