# DMP Flowable - ETL 完整開發與維運技術手冊

這份文件整合了本系統從基礎架構、開發環境、目錄結構、核心程式碼、維運稽核、到開發擴充 SOP 的所有細節。旨在讓任何層級的開發者（甚至是對 ClickHouse 不熟悉的新手）都能快速上手並進行維護。

---

## 第零部分：快速開始 - 開發環境準備

在開始閱讀代碼前，請先確保您的開發環境已就緒：

1.  **安裝依賴套件**：
    在專案根目錄執行：`pip install -r requirements-dev.txt`。
2.  **資料庫連線資訊**：
    連線設定通常位於 `scripts/etl/` 下各 Python 檔案頂部的 `CH_CONFIG` 變數中，或透過環境變數設定。請確保您的電腦可以連通 `REDACTED_IP`。
3.  **推薦工具**：
    建議安裝 **DBeaver** 並設定 ClickHouse 驅動，方便手動執行 SQL 進行數據驗證。

---

## 第一部分：執行引擎與檔案路徑映射

為了讓開發者快速定位程式碼，請參考下方的目錄樹結構。整個 ETL 系統是由「執行程式」、「系統設定」與「SQL 邏輯」三個部分組成的：

### 專案核心目錄樹 (ETL 相關)

```text
dmp_flowable/
├── scripts/
│   └── etl/                        (1) 程式執行處：所有的 Python 執行引擎
│       ├── daily_etl_wrapper.sh      --> 日常排程總入口 (Shell)
│       ├── setup_schema.py           --> 初始化建表程式
│       ├── sync_unified_odbc.py      --> 資料搬運同步程式
│       ├── execute_etl.py            --> SQL 邏輯運算程式
│       └── config/                  (2) 系統設定處：所有的 YAML 設定檔
│           ├── infra_config.yaml      --> 建表清單設定
│           ├── pipeline_config.yaml   --> 計算管線順序設定
│           └── sync_tables.yaml       --> 來源表映射與同步策略
└── sql/
    └── etl/
        ├── schema/                  (3) 結構定義處：所有的 DDL 建表語法
        │   ├── 00_meta_checkpoint.sql
        │   ├── 01_bronze_...sql
        │   └── 04_silver_...sql
        └── dml/                     (4) 業務邏輯處：所有的 DML 運算語法
            ├── backfill_pivot.sql          --> 變數轉置邏輯
            ├── backfill_silver.sql         --> 核心寬表與清洗邏輯
            ├── backfill_gold_...sql        --> KPI 指標計算邏輯
            └── backfill_gold_summary.sql   --> ★ Cube.js 整數預聚合（最終步驟）
```

### 各階段執行映射表

| 執行階段 | Python 腳本 (scripts/etl/) | 讀取的設定 (config/) | 核心 SQL 位置 |
| :--- | :--- | :--- | :--- |
| **初始化建表** | `setup_schema.py` | `infra_config.yaml` | `sql/etl/schema/*.sql` |
| **Bronze 擷取** | `sync_unified_odbc.py` | `sync_tables.yaml` | (由 Python 動態產生) |
| **Silver/Gold 運算** | `execute_etl.py` | `pipeline_config.yaml` | `sql/etl/dml/*.sql` |
| **資料對帳驗證** | `audit_done_details.py` | (手動輸入參數) | `silver.mv_fact_task_vx` |

---

## 第二部分：系統架構與資料分層概念 (Medallion Architecture)

本系統採用獎牌架構，確保資料可追溯且運算高效：

| 層級 | 名稱 | 檔案路徑範例 | 核心目的 |
| :--- | :--- | :--- | :--- |
| **Bronze** | **原始層** | `schema/01_...` | 1:1 複製 MSSQL 原始資料，保留歷史真相。 |
| **Silver** | **事實層** | `dml/backfill_silver.sql` | **核心區域**。處理變數轉置、大表 JOIN、資料清理。 |
| **Gold** | **指標層** | `dml/backfill_gold.sql` | KPI Bitmap 物理化，供 FastAPI 直接查詢。 |
| **Gold Summary** | **預聚合層** | `dml/backfill_gold_summary.sql` | **★ Cube.js 查詢入口**。Bitmap 轉整數預聚合，查詢耗時 < 0.11s。 |

---

## 第三部分：Bronze 層資料擷取與穩定性機制

Bronze 層的任務是利用 ClickHouse 的 ODBC 功能進行跨庫同步，由核心程式 `sync_unified_odbc.py` 負責：

*   **顯式 DDL 代理表機制 (Explicit DDL Proxy)**：
    這是本系統最關鍵的同步技術。我們不直接使用單純的 `odbc()` 函數，而是先建立一個「顯式定義欄位」的暫時代理表：
    ```python
    # 程式碼實作邏輯 (sync_unified_odbc.py)
    create_sql = f"CREATE TABLE temp_odbc ( {engine_ddl} ) ENGINE = ODBC('DSN=...', 'schema', 'table')"
    ```
    *   **為什麼這樣做？**：原生 ODBC 驅動在自動偵測 MSSQL 欄位（特別是 `varchar(max)` 或 `xml` 等 LOB 欄位）時極不穩定，且容易造成 MSSQL 端鎖表 (Deadlock)。透過在 `sync_tables.yaml` 中預先定義好 `{engine_ddl}`，我們可以強制 ClickHouse 以安全的方式讀取資料。
*   **資料追加邏輯 (Append Logic)**：
    建立代理表後，執行 `INSERT INTO bronze_table SELECT ... FROM temp_odbc`。
*   **同步策略**：
    *   **全量 (Full Sync)**：用於人員或組織主檔，每次 `TRUNCATE` 後重新抓取。
    *   **增量 (Batch Append)**：用於任務流水帳。利用 **Watermark (水位線)** 機制只抓取 `ModifyDate` 比 ClickHouse 中最新日期更晚的新資料。
*   **適應性分切 (Adaptive Splitting)**：若同步大表時遇到記憶體溢位 (OOM)，腳本會自動將時間範圍「切半遞迴」執行並重試，確保在低記憶體環境也能處理千萬級數據。

---

## 第四部分：Silver 層變數轉置與事實整合邏輯

### 1. 變數轉置 (Pivot) - `backfill_pivot.sql`
Flowable 的業務變數是以 Key-Value 存儲，我們利用 `argMaxIf` 將其轉為欄位：
```sql
SELECT PROC_INST_ID_, argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'moNumber') AS varinst_moNumber
FROM bronze.bpm_act_hi_varinst v GROUP BY v.PROC_INST_ID_
```

### 2. 事實寬表整合 (mv_fact_task_vx)
目前整合了 `taskinst`、`procinst`、`hr_employee`、`mv_varinst_pivoted` 與 MDM 主檔。
*   **未來擴充**：若要加入新表，需在 `backfill_silver.sql` 新增 `LEFT JOIN` 並同步修改 `schema/04_...` 建表 SQL。

---

## 第五部分：核心業務邏輯代碼展示 (開發重點)

### 1. 結算狀態判定 (Cohort Logic)
利用 `toStartOfWeek` 鎖死開單週，確保跨週任務的報表正確。
```sql
CASE WHEN t.END_TIME_ IS NOT NULL AND toDate(t.END_TIME_) <= (toStartOfWeek(toDate(t.START_TIME_), 3) + INTERVAL 6 DAY) 
     THEN 'DONE' ELSE 'TODO' END AS status_weekly
```

### 2. 排除規則 (Exclusion Rules)
使用 `multiIf` 統一過濾無效任務（例如排除測試工單 `Q%`）：
```sql
multiIf(
    tb.LONG_ = 1, 1,                                            -- 自動完成節點
    (COALESCE(v_pivot.varinst_moNumber, '') LIKE 'Q%'), 1,       -- 測試工單
    0) AS is_excluded
```

### 3. L5 指標專題：Acc 負荷量實作
利用 `ARRAY JOIN` 將任務展開 7 天，計算每日當下的 WIP：
```sql
SELECT snapshot_date, groupBitmapStateIf(cityHash64(task_id), task_end_date IS NULL OR task_end_date > toDate(active_date_raw)) AS acc
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayDistinct(range(toUInt32(task_start_date), toUInt32(task_start_date + 7))) AS active_date_raw
GROUP BY snapshot_date
```

---

## 第六部分：維運監控與稽核機制

### 1. 執行紀錄表 (ops_metrics.etl_checkpoint)
記錄每次計算的進度。如果您的數據沒更新，請先查詢此表確認 `status` 是否為 `SUCCESS`。

### 2. 資料對帳工具 (audit_done_details.py)
當 KPI 數字有疑慮時，可執行此工具拉出詳細明細進行對帳：
```bash
python scripts/etl/audit_done_details.py --date 2026-05-12 --status done
```

---

## 第七部分：開發者日常工作流 - SQL 與 Python 的配合機制

新手必須理解：在本系統中，「邏輯修改」與「執行應用」是分開的。這是一個「模板驅動」的設計。

### 1. SQL 負責「算什麼」(業務邏輯)
當業務需求變更（例如：新增排除規則、修改 KPI 公式）時，您的主要戰場在 `sql/etl/` 資料夾：
*   **修改方式**：直接編輯 `.sql` 檔案。
*   **測試方式**：您可以將 SQL 代碼複製到 **DBeaver** 中，手動取代變數（如 `{start_ts}`）來驗證結果是否正確。

> **實作範例**：
> 假設 SQL 模板中有一段：
> ```sql
> SELECT count(*) FROM silver.mv_fact_task_vx WHERE task_start_date >= '{start_ts}'
> ```
> 您在 DBeaver 測試時，應將其修改為具體日期（注意保留單引號）：
> ```sql
> SELECT count(*) FROM silver.mv_fact_task_vx WHERE task_start_date >= '2026-05-01'
> ```

### 2. Python 負責「怎麼跑」(自動化執行)
當 SQL 修改好之後，並不會自動生效。您必須透過 `scripts/etl/` 下的 Python 程式來發動：
*   **讀取模板**：Python 程式（如 `execute_etl.py`）會讀取您改好的 SQL 檔案作為「模板」。
*   **注入變數**：程式會自動幫您注入時間參數、處理 OOM 分段、並記錄 Checkpoint。
*   **執行流程**：
    1.  **Step 1 (編輯 SQL)**：改好 `dml/backfill_silver.sql`。
    2.  **Step 2 (執行程式)**：在終端機執行 `python scripts/etl/execute_etl.py --daily`。
    3.  **Step 3 (驗收結果)**：檢查資料庫或 Checkpoint 表。

> **核心準則**：先修邏輯 (SQL)，再跑任務 (Python)。永遠不要手動在資料庫裡寫死邏輯，否則下次自動化排程執行時，您的修改會被覆蓋。

---

## 第八部分：快速擴充 SOP (標準作業程序)

### 情境 A：新增原始表 (MSSQL -> Bronze)
1. 在 `sql/etl/schema/` 建立建表 SQL。
2. 在 `infra_config.yaml` 註冊該 SQL 並執行 `setup_schema.py`。
3. 在 `sync_tables.yaml` 定義 MSSQL 來源欄位。
4. 執行 `python scripts/etl/sync_unified_odbc.py --table <表名>`。

### 情境 B：新增一個全新的 KPI 指標
1. 建立 Gold 層實體表 SQL → 註冊 `infra_config.yaml` → 執行 `setup_schema.py`。
2. 撰寫運算邏輯 DML (`backfill_new_kpi.sql`)。
3. 在 `pipeline_config.yaml` 註冊新的運算步驟。
4. 若指標需由 Cube.js 查詢，在 `backfill_gold_summary.sql` 中新增對應欄位，並更新 `schema/06b_gold_kpi_task_summary.sql` DDL。
5. 執行 `python scripts/etl/execute_etl.py --daily`。

---

## 第九部分：新手練習建議 - 您的第一個維護任務

為了讓您快速熟悉系統，建議您嘗試完成以下三個實戰練習。這將涵蓋日常維護中 80% 的操作場景：

### 練習 1：邏輯與執行的完整循環
*   **任務內容**：在 `sql/etl/dml/backfill_silver.sql` 中新增一個 `Notify` 類型的節點排除規則（參考 `multiIf` 段落），並執行 `python scripts/etl/execute_etl.py --daily`。
*   **預期結果**：能在 `ops_metrics.etl_checkpoint` 表中看到該段時間區間顯示為 `SUCCESS`，且 `silver.mv_fact_task_vx` 中的資料筆數符合預期。
*   **目的**：熟悉「SQL 修改 -> Python 執行 -> Checkpoint 驗收」的完整開發閉環。

### 練習 2：維度溯源與查帳追蹤
*   **任務內容**：挑選 Gold 層中的一個五階維度欄位（例如 `plant`），嘗試從 `backfill_gold_...sql` 回溯到 `backfill_silver.sql`，再追蹤到 `backfill_pivot.sql`，最後找出它在 MSSQL `ACT_HI_VARINST` 表中對應的原始變數名稱。
*   **預期結果**：能畫出該欄位的資料流向圖。
*   **目的**：熟悉資料血緣。當業務單位對數據有疑問時，您能迅速定位是哪一層的邏輯出了問題。

### 練習 3：異常恢復與同步重置
*   **任務內容**：手動刪除 `bronze._sync_watermark` 表中關於 `taskinst` 的同步紀錄，然後重新執行 `python scripts/etl/sync_unified_odbc.py --table taskinst`。
*   **預期結果**：觀察 Python 日誌，確認系統是否從頭（或指定的水位線）重新拉取資料。
*   **目的**：熟練掌握「Watermark 重置」技巧。這是當來源端資料有變動或同步發生遺漏時，最核心的修復手段。

---

## 第十部分：重要技術術語表與 FAQ

為了讓開發者能與本系統的設計思想對齊，以下列出核心技術術語與常見問題。

### 1. 核心術語表 (Glossary)
*   **ReplacingMergeTree**：ClickHouse 的一種資料表引擎。它會在背景自動合併具有相同主鍵的資料，並保留最新版本。這讓我們不需要寫複雜的 `UPDATE` 語法，只需不斷 `INSERT` 即可。
*   **argMax(a, b)**：取出去重後的最新值。當有多筆重複資料時，取 `b` 最大的那一筆資料的 `a` 欄位。常用於事實表去重。
*   **groupBitmapState**：ClickHouse 用於處理千萬級去重計數的語法。它將 ID 轉為二進位位圖 (Bitmap)，佔用空間極小且運算速度極快（常用於 L5 指標）。
*   **ODBC Table Function**：跨庫抓取技術。讓 ClickHouse 像連線一張本地表一樣，直接讀取遠端 MSSQL 的資料。
*   **FINAL 關鍵字**：在 `FROM table FINAL` 語法中，強制 ClickHouse 在查詢當下即時合併重複資料，確保查詢結果 100% 精準。

### 2. 常見問題 FAQ
*   **Q：為什麼我查出來的資料筆數變多了（有重複）？**
    *   A：ClickHouse 是背景合併資料。請在 SQL 中加入 `FINAL` 關鍵字，或使用 `GROUP BY` 搭配 `argMax` 來取出最新版本。
*   **Q：為什麼我修改了 DML 並執行了 Python，但資料庫數字沒變？**
    *   A：請檢查 `ops_metrics.etl_checkpoint`。如果該時段的狀態已經是 `SUCCESS`，Python 會自動跳過運算。若要強迫重跑，請刪除該筆 Checkpoint 紀錄或使用 `--reset` 參數。
*   **Q：同步時出現 Memory Limit Exceeded (OOM) 怎麼辦？**
    *   A：系統會自動嘗試「適應性分切」。如果還是失敗，請在執行 Python 時加上 `--low-ram` 參數，或縮短 `--step-days` 的天數。
*   **Q：如何確認 MSSQL 的資料已經成功搬進來了？**
    *   A：請查詢 `bronze._sync_watermark` 表，裡面記錄了每一張原始表最後一次成功同步的時間點。
