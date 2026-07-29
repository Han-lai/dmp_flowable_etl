# ETL 轉換管線技術細節 (Bronze → Silver → Gold)

**文件編號**: 03-ETL-001  
**最後更新**: 2026-07-02  
**狀態**: 正式發布 (Released)  
**維護者**: AIT / Data Engineering

---

## 目錄 (Table of Contents)

1. [管線總覽](#1-管線總覽)
2. [Stage 1 — EAV 變數轉置 (backfill_pivot.sql)](#2-stage-1--eav-變數轉置-backfill_pivotsql)
3. [Stage 2 — 核心事實表建構 (backfill_silver.sql)](#3-stage-2--核心事實表建構-backfill_silversql)
4. [Stage 2b — 排除規則補標 (backfill_exclusion.sql)](#4-stage-2b--排除規則補標-backfill_exclusionsql)
5. [Stage 4 — 里程碑快照聚合 (backfill_gold_milestone.sql)](#5-stage-4--里程碑快照聚合-backfill_gold_milestonesql)
6. [Stage 5 — ACC 七日滾動去重 (backfill_gold_acc.sql)](#6-stage-5--acc-七日滾動去重-backfill_gold_accsql)
7. [Stage 6 — 最終合併主表 (backfill_gold.sql)](#7-stage-6--最終合併主表-backfill_goldsql)
8. [Stage 7 — 歷史資料預聚合 (backfill_gold_summary_historical.sql)](#8-stage-7--歷史資料預聚合-backfill_gold_summary_historicalsql)（新增於 2026-06-10）
9. [Stage 8 — 增量預聚合彙總表 (backfill_gold_summary.sql)](#9-stage-8--增量預聚合彙總表-backfill_gold_summarysql)
10. [時間視窗機制與 Checkpoint](#10-時間視窗機制與-checkpoint)
10. [維護作業參考](#10-維護作業參考)

---

## 1. 管線總覽

Bronze 層資料就緒後，`execute_etl.py` 依 `pipeline_config.yaml` 定義的階段順序，
透過「時間視窗批次」驅動 8 個 SQL 步驟，將資料逐步轉換至 Gold 層。

```
Bronze 層 (19 張原始表：15 full + 4 batch)
        │
        │  execute_etl.py --backfill --step-days 10
        │  取 pipeline_config.yaml 定義的執行順序
        │
Stage 1 ▼  backfill_pivot.sql
        silver.mv_varinst_pivoted
        (EAV → 寬表轉置，每個 PROC_INST_ID_ 一列)
        │
Stage 2 ▼  backfill_silver.sql
        silver.mv_fact_task_vx
        (核心事實表：JOIN 任務/變數/維度/人員)
        │
Stage 2b▼  backfill_exclusion.sql
        silver.mv_fact_task_vx (UPDATE is_excluded)
        (補標 autoComplete 排除旗標)
        │
        ├─── Stage 4 ▼  backfill_gold_milestone.sql
        │              gold.rmv_l5_milestone_phys
        │              (ARRAY JOIN 展開快照，計算 Todo/Doing/Done)
        │
        ├─── Stage 5 ▼  backfill_gold_acc.sql
        │              gold.rmv_l5_acc_phys
        │              (range() 展開活躍日期，計算 7 日滾動在途 acc 與總量 acc_total_task)
        │
Stage 6 ▼  backfill_gold.sql
        gold.rmv_l5_task_completion_phys
        (FULL OUTER JOIN 合併 Milestone + ACC)
        │
        │  gold.rmv_l5_task_completion  (VIEW + FINAL)
        │  (FastAPI 查詢入口)
        │
Stage 7 ▼  backfill_gold_summary_historical.sql              （新增於 2026-06-10）
        gold.rmv_l5_task_summary
        (歷史資料 ≤2026-03-31：混合粒度 Day/event + Week/Month Cohort，Bitmap→整數)
        │
Stage 8 ▼  backfill_gold_summary.sql
        gold.rmv_l5_task_summary
        (★ 增量 ≥2026-04-01：純 Cohort，Bitmap→整數，V4 Pre-aggregation 2026-05-27 起)
```

**SQL 模板位置**: `sql/etl/dml/`  
**執行引擎**: `scripts/etl/execute_etl.py`  
**階段設定**: `scripts/etl/config/pipeline_config.yaml`

---

## 2. Stage 1 — EAV 變數轉置 (backfill_pivot.sql)

### 2.1 目的

`ACT_HI_VARINST` 以 Entity-Attribute-Value（EAV）格式儲存每個流程實例的業務變數，每個屬性一列。Stage 1 將同一 `PROC_INST_ID_` 的多列屬性合併為單列寬表，供後續 JOIN 使用。

### 2.2 輸入 / 輸出

| 項目     | 內容                                                |
| :------- | :-------------------------------------------------- |
| **輸入** | `bronze.bpm_act_hi_taskinst` (確定活躍視窗範圍)     |
| **輸入** | `bronze.bpm_act_hi_varinst` (EAV 原始資料)          |
| **輸出** | `silver.mv_varinst_pivoted`                         |
| **粒度** | 每個 `PROC_INST_ID_` 一列                           |

### 2.3 核心邏輯

```sql
-- 步驟 1: 先從 taskinst 找出本視窗有活動的 PROC_INST_ID_
WITH target_procs AS (
    SELECT DISTINCT PROC_INST_ID_
    FROM bronze.bpm_act_hi_taskinst
    WHERE (START_TIME_  >= '{start_ts}' AND START_TIME_  <= '{end_ts}')
       OR (CLAIM_TIME_  >= '{start_ts}' AND CLAIM_TIME_  <= '{end_ts}')
       OR (END_TIME_    >= '{start_ts}' AND END_TIME_    <= '{end_ts}')
)
-- 步驟 2: 只對活躍的 PROC_INST_ID_ 做 EAV Pivot
INSERT INTO silver.mv_varinst_pivoted
SELECT
    v.PROC_INST_ID_,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'region')      AS varinst_region,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'plant')       AS varinst_plant,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'factory')     AS varinst_factory,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'lineName')    AS varinst_lineName,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'moNumber')    AS varinst_moNumber,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'modelName')   AS varinst_modelName,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'deliveryArea') AS varinst_deliveryArea,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'scheduleNumber') AS varinst_scheduleNumber,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'sapPlant')    AS varinst_sapPlant,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'sapProductGroup') AS varinst_sapProductGroup,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'pallet')      AS varinst_pallet,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'transferNo')  AS varinst_transferNo,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'qBlockEventId') AS varinst_qBlockEventId,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'defectSn')    AS varinst_defectSn,
    argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'time')        AS varinst_time,
    argMaxIf(if(v.LONG_ = 1,'true','false'), v.REV_,
             v.NAME_ = 'autoComplete')                 AS varinst_autoComplete
FROM bronze.bpm_act_hi_varinst v
INNER JOIN target_procs t ON v.PROC_INST_ID_ = t.PROC_INST_ID_
WHERE v.NAME_ IN ('region','plant','factory','lineName','moNumber','modelName','deliveryArea','scheduleNumber','sapPlant','sapProductGroup','pallet','transferNo','qBlockEventId','defectSn','time','autoComplete')
  AND v.CREATE_TIME_ >= parseDateTimeBestEffort('{start_ts}') - INTERVAL 365 DAY
  AND v.CREATE_TIME_ <= '{end_ts}'
GROUP BY v.PROC_INST_ID_
```

**關鍵設計說明**：

- **`argMaxIf`**：取同一屬性中 `REV_` 最大（最新）的值，處理流程變數被更新的情境。
- **`INNER JOIN target_procs`**：只處理本視窗有任務活動的流程實例，大幅縮小掃描量。
- **`INTERVAL 365 DAY`**：流程變數可能在任務開始前很久就已寫入（長期流程），故向前延伸查找。2026-06-04（`d8ade48`）由原 180 天延長至 365 天，覆蓋超過半年的長流程任務。

---

## 3. Stage 2 — 核心事實表建構 (backfill_silver.sql)

### 3.1 目的

建立 `silver.mv_fact_task_vx`，為系統的核心事實表。每列代表一個任務實例，整合了任務時間戳記、Vx 版本歸屬、五階製造維度、排除規則旗標及人員姓名。

### 3.2 輸入 / 輸出

| 項目     | 內容                                                   |
| :------- | :----------------------------------------------------- |
| **輸入** | `bronze.bpm_act_hi_taskinst` (主表)                    |
| **輸入** | `silver.mv_varinst_pivoted` (Stage 1 產出)             |
| **輸入** | `silver.mv_dim_mfg_five_level` (五階維度，由 DDL 建立) |
| **輸入** | `bronze.common_hr_employee` (人員姓名)                 |
| **輸入** | `bronze.bpm_act_hi_varinst` (autoComplete 旗標)        |
| **輸出** | `silver.mv_fact_task_vx`                               |
| **粒度** | 每個 `task_id` 一列                                    |

### 3.3 Vx 版本歸屬邏輯

優先序由高至低：

```
優先序 1: 特定工單號規則
  條件: substring(mo_number, 1, 3) IN ('196','199','200','210','212','213')
  → 強制歸類為 V1

優先序 2: TASK_DEF_KEY_ 前綴判定
  TASK_DEF_KEY_ LIKE 'V1%' → V1
  TASK_DEF_KEY_ LIKE 'V2%' → V2
  TASK_DEF_KEY_ LIKE 'V3%' → V3

優先序 3: 無法判定
  → 取 substring(TASK_DEF_KEY_, 1, 2) 或回填 'Unknown'
```

**變更歷史**:
- 2026-04-15: 簡化規則，移除 DG3/NPE 廠區限制條件（冗餘）
- 2026-02-26: 新增 DG3/NPE 廠區特權規則（已移除）

### 3.4 五階維度補齊邏輯

維度資料以 VARINST 為優先，MDM 主檔為 Fallback：

```sql
COALESCE(NULLIF(v_pivot.varinst_region, ''),  mdm.region_code,   plant_mdm.region_code, 'UNKNOWN') AS region
COALESCE(NULLIF(v_pivot.varinst_plant, ''),   mdm.plant_code,    'UNKNOWN')                        AS plant
COALESCE(NULLIF(v_pivot.varinst_factory, ''), mdm.factory_code,  'UNKNOWN')                        AS factory
COALESCE(NULLIF(v_pivot.varinst_lineName,''), mdm.line_name,     'UNKNOWN')                        AS line
```

同時寫入 `region_source` / `plant_source` 等欄位，記錄維度來源（`VARINST` / `MDM` / `MISSING`），方便資料品質稽核。

### 3.5 排除規則旗標 (is_excluded)

| 條件 | `is_excluded` | `exclude_reason` |
| :--- | :-----------: | :--------------- |
| `autoComplete = 1` (varinst LONG_ = 1) | 1 | `bypass` |
| `TASK_DEF_KEY_ LIKE 'E%'` 或 `'C%'` | 1 | `system_node` |
| `mo_number LIKE 'Q%'` | 1 | `Q_order` |
| `mo_number LIKE 'R%'` | 1 | `R_order` |
| `NAME_ LIKE '%Notify%'` | 1 | `notify_task` |
| `NAME_ LIKE '%Dummy%'` | 1 | `dummy_task` |
| 以上均不符合 | 0 | `''` |

### 3.6 視窗過濾條件 (Triple-OR)

任務的三個時間點（Start / Claim / End）只要其中一個落在視窗內，即納入本批次：

```sql
WHERE (t.START_TIME_ >= '{start_ts}' AND t.START_TIME_ <= '{end_ts}')
   OR (t.CLAIM_TIME_ >= '{start_ts}' AND t.CLAIM_TIME_ <= '{end_ts}')
   OR (t.END_TIME_   >= '{start_ts}' AND t.END_TIME_   <= '{end_ts}')
```

---

## 4. Stage 2b — 排除規則補標 (backfill_exclusion.sql)

### 4.1 目的

Stage 2 已在插入時標記大多數排除規則，但 `autoComplete` 的狀態可能在任務建立後才由使用者設定（非同時寫入）。Stage 2b 透過 `ALTER TABLE ... UPDATE` 針對本視窗的任務重新掃描，補標被遺漏的 `autoComplete` 排除旗標。

### 4.2 核心邏輯

```sql
ALTER TABLE silver.mv_fact_task_vx
UPDATE is_excluded = 1, exclude_reason = 'autoComplete_flag'
WHERE task_id IN (
    SELECT TASK_ID_
    FROM bronze.bpm_act_hi_varinst
    WHERE NAME_ = 'autoComplete' AND LONG_ = 1
      AND TASK_ID_ IN (
          SELECT DISTINCT ID_
          FROM bronze.bpm_act_hi_taskinst
          WHERE (START_TIME_ >= ... AND START_TIME_ <= ...)
             OR (CLAIM_TIME_ >= ... AND CLAIM_TIME_ <= ...)
             OR (END_TIME_   >= ... AND END_TIME_   <= ...)
      )
)
```

> **注意**：`ALTER TABLE ... UPDATE` 在 ClickHouse 中為異步 Mutation 操作，執行後資料不會立即可見，需等待 Merge 完成。Gold 層 Stage 4 之後才讀取 Silver，因此時序上不會造成問題。

---

## 5. Stage 4 — 里程碑快照聚合 (backfill_gold_milestone.sql)

### 5.1 目的

將核心事實表的任務生命週期事件，預聚合為「同日結算 (Same-Day Cohort)」的 Bitmap 快照，計算 Todo / Doing / Done 三種狀態集合。

### 5.2 核心邏輯：開單日錨定 (Cohort)

V4.3 架構捨棄了耗費資源的 `ARRAY JOIN`，改採嚴格的開單日錨定邏輯。每筆任務只會在 `task_start_date` 當天出現一次：

```sql
FROM silver.mv_fact_task_vx FINAL
GROUP BY task_start_date AS snapshot_date
```

### 5.3 狀態判定公式 (Bitmap)

在 `task_start_date` 這個唯一的快照點上，透過 `groupBitmapStateIf` 搭配 `cityHash64(task_id)`，將符合條件的任務 ID 寫入 Bitmap：

```sql
-- Todo: 當日開單，但未被領取（或非當日領取）
todo_daily = groupBitmapStateIf(cityHash64(task_id), 
    COALESCE(task_claim_date, toDate('1900-01-01')) != task_start_date 
    AND (task_end_date IS NULL OR task_end_date != task_start_date))

-- Doing: 當日開單且當日領取，但非當日完工
doing_daily = groupBitmapStateIf(cityHash64(task_id), 
    task_claim_date = task_start_date 
    AND (task_end_date IS NULL OR task_end_date != task_start_date))

-- Done: 當日開單，且當日完結 (Same-Day Completion)
done_daily = groupBitmapStateIf(cityHash64(task_id), 
    task_end_date = task_start_date)
```
> **注意**：另外還有 `_weekly` 與 `_monthly` 系列 Bitmap，會根據 ISO 週與自然月邊界自動判斷。

---

## 6. Stage 5 — ACC 七日滾動去重 (backfill_gold_acc.sql)

### 6.1 目的

計算 7 日滾動視窗內仍處於在途（Todo + Doing）狀態的任務集合（ACC, Accumulated），以及該滾動視窗內的總開單任務集合（Acc Total Task）。

### 6.2 核心邏輯：range() 展開活躍日期

ACC 需要追蹤 7 天，因此仍使用 `range()` 與 `ARRAY JOIN` 將任務展開為最多 7 天的活躍日期：

```sql
ARRAY JOIN arrayDistinct(
    range(toUInt32(task_start_date), toUInt32(least(COALESCE(task_end_date, today() + 1), task_start_date + 7)))
) AS active_date_raw
WHERE (task_end_date IS NULL OR task_end_date > toDate(active_date_raw))
```

展開後，同樣使用 `groupBitmapState` 寫入 Bitmap，避免了使用 `uniqExact` 造成的無法跨維度疊加問題：

```sql
SELECT
    toDate(active_date_raw) AS snapshot_date,
    ...
    groupBitmapStateIf(cityHash64(task_id), task_end_date IS NULL OR task_end_date > toDate(active_date_raw)) AS acc,
    groupBitmapState(cityHash64(task_id)) AS acc_total_task
GROUP BY snapshot_date, ...
```

---

## 7. Stage 6 — 最終合併主表 (backfill_gold.sql)

### 7.1 目的

將 Milestone（Todo/Doing/Done）與 ACC（7日在途量）兩個獨立計算結果，透過 `LEFT JOIN` 合併至最終金層實體表 `rmv_l5_task_completion_phys`。

### 7.2 核心邏輯 (Bitmap 合併)

由於底層儲存改為 Bitmap，總任務數 `total_task` 不再是整數相加，而是使用 `bitmapOr` 將子狀態做聯集：

```sql
INSERT INTO gold.rmv_l5_task_completion_phys
SELECT
    m.snapshot_date,
    ...
    bitmapOr(bitmapOr(m.todo_daily, m.doing_daily), m.done_daily) AS total_task,
    m.todo_daily, m.doing_daily, m.done_daily,
    ...
    a.acc
FROM gold.rmv_l5_milestone_phys AS m
LEFT JOIN gold.rmv_l5_acc_phys AS a 
    ON m.snapshot_date = a.snapshot_date AND ...
```

### 7.3 BI 對接視圖

FastAPI 透過 `rmv_l5_task_completion` (VIEW + FINAL) 讀取，執行即時 `bitmapCardinality(groupBitmapMergeState(...))` 去重聚合。

**Cube.js** 改為讀取 Stage 7 產出的 `rmv_l5_task_summary`，直接 `SUM` 整數欄位，查詢耗時從 ~750ms 降至 0.06~0.11 秒。

---

## 8. Stage 7 — 預聚合彙總表 (backfill_gold_summary.sql)

### 8.1 目的

將 `rmv_l5_task_completion_phys` 中的 Bitmap 欄位，在 ETL 寫入時即轉換為整數，按 `period_type`（Day / Week / Month）× `period_key` × 五階維度儲存，讓 Cube.js 查詢降為純 `SUM` 運算，消除即時 Bitmap 聚合的開銷。

### 8.2 輸入 / 輸出

| 項目     | 內容                                              |
| :------- | :------------------------------------------------ |
| **輸入** | `gold.rmv_l5_task_completion_phys` (Stage 6 產出) |
| **輸出** | `gold.rmv_l5_task_summary`                        |
| **粒度** | `period_type` × `period_key` × 五階維度 × `vx_type` |

### 8.3 核心欄位

| 欄位名稱        | 說明                                            |
| :-------------- | :---------------------------------------------- |
| `period_type`   | `'Day'` / `'Week'` / `'Month'`                  |
| `period_key`    | `'2025-12-31'` / `'2025-W52'` / `'2025-12'`    |
| `snapshot_date` | 對應該 period 的代表日（Day=當日，Week/Month=最後一天） |
| `total_qty`     | `bitmapCardinality(groupBitmapMergeState(total_task))`  |
| `todo_qty`      | `bitmapCardinality(groupBitmapMergeState(todo_daily))`  |
| `doing_qty`     | `bitmapCardinality(groupBitmapMergeState(doing_daily))` |
| `done_qty`      | `bitmapCardinality(groupBitmapMergeState(done_daily))`  |
| `acc_qty`       | `bitmapCardinality(groupBitmapMergeState(acc))`         |
| `acc_total_qty` | `bitmapCardinality(groupBitmapMergeState(acc_total_task))` |

### 8.4 增量視窗擴展設計

Week / Month 粒度的視窗邊界由 `toStartOfWeek` / `toStartOfMonth` 動態擴展，確保 `ReplacingMergeTree` 能覆蓋完整週期，避免增量執行時遺漏歷史資料。

---

## 9. 時間視窗機制與 Checkpoint  

### 8.1 視窗切割方式

`execute_etl.py` 依 `--step-days` 參數將整個日期範圍切割為等長視窗，逐一執行：

```
--start 2025-01-01  --end 2025-12-31  --step-days 10

視窗 1:  2025-01-01 00:00:00  ~  2025-01-10 23:59:59
視窗 2:  2025-01-11 00:00:00  ~  2025-01-20 23:59:59
...
視窗 37: 2025-12-22 00:00:00  ~  2025-12-31 23:59:59

每個視窗 × 8 個 SQL 步驟 = 296 次 SQL 執行
```

### 8.2 Checkpoint 斷點續傳

每個 `(phase_id, window_start, window_end)` 組合執行成功後，寫入 `ops_metrics.etl_checkpoint`：

```sql
-- 查詢最近執行狀態
SELECT phase, window_start, window_end, status,
       round(duration_ms/1000, 2) AS dur_sec, result_rows
FROM ops_metrics.etl_checkpoint FINAL
ORDER BY update_time DESC
LIMIT 30;
```

程式重啟時自動跳過狀態為 `SUCCESS` 的視窗，從失敗處續跑。

### 8.3 OOM 自動分裂

當視窗執行觸發 `Memory limit exceeded (Code: 241)`，且視窗長度 > 60 秒時，自動切半遞迴重試：

```
視窗 10 天觸發 OOM
  → 切為 5+5 天
     → 若 5 天仍 OOM，切為 2.5+2.5 天（繼續遞迴）
        → 最小粒度: 60 秒
```

---

## 10. 維護作業參考

### 9.1 全量重算（修改業務邏輯後）

當 Vx 歸屬邏輯、排除規則或 SQL 模板有變動時，需執行全量重算：

```bash
# 清空 Silver/Gold 所有物理表 + Checkpoint，從頭重算
python scripts/etl/execute_etl.py --backfill --reset --start 2025-01-01 --low-ram --step-days 10
```

> **注意**：`--reset` 會執行 `pipeline_config.yaml` 的 `reset_targets` 清單下所有表的 `TRUNCATE`，操作不可逆。

### 9.2 每日增量更新

```bash
# 自動回溯最近 7 天（任務可能在這段時間狀態有變化）
python scripts/etl/execute_etl.py --daily --low-ram
```

### 9.3 補算指定日期區間

```bash
# 不清空現有資料，僅補算指定範圍（ReplacingMergeTree 自動去重）
python scripts/etl/execute_etl.py --backfill --start 2025-03-01 --end 2025-03-31 --low-ram
```

### 9.4 稽核查詢：各表列數確認

```sql
-- 快速確認各層資料量
SELECT 'silver.mv_fact_task_vx'           AS tbl, count() FROM silver.mv_fact_task_vx FINAL
UNION ALL
SELECT 'gold.rmv_l5_milestone_phys'       AS tbl, count() FROM gold.rmv_l5_milestone_phys FINAL
UNION ALL
SELECT 'gold.rmv_l5_acc_phys'             AS tbl, count() FROM gold.rmv_l5_acc_phys FINAL
UNION ALL
SELECT 'gold.rmv_l5_task_completion_phys' AS tbl, count() FROM gold.rmv_l5_task_completion_phys FINAL;
```

### 9.5 稽核查詢：特定日期維度驗證

```sql
-- 驗證特定日期、特定維度的 Gold 層輸出
SELECT snapshot_date, vx_type, plant, factory, line,
       total_task, todo_count, doing_count, done_count, acc_todo_doing
FROM gold.rmv_l5_task_completion FINAL
WHERE snapshot_date = '2025-12-31'
  AND vx_type = 'V3'
  AND factory = 'NBU'
ORDER BY line;
```

---

## 相關文件

| 文件 | 路徑 |
| :--- | :--- |
| SQL 模板原始碼 | `sql/etl/dml/backfill_*.sql` |
| 管線階段設定 | `scripts/etl/config/pipeline_config.yaml` |
| 執行引擎原始碼 | `scripts/etl/execute_etl.py` |
| 業務指標定義 | `docs/03_metrics/Metrics_and_Data_Definitions.md` |
| 系統架構總覽 | `docs/01_architecture/Architecture_Overview.md` |

---

**文件負責人**: AIT / Data Engineering  
**審核狀態**: 已對照 `sql/etl/dml/` 下所有 SQL 模板及 `execute_etl.py` 執行邏輯驗證完成
