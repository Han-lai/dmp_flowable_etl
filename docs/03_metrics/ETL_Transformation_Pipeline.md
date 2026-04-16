# ETL 轉換管線技術細節 (Bronze → Silver → Gold)

**文件編號**: 03-ETL-001  
**版本**: 1.0  
**最後更新**: 2026-04-14  
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
8. [時間視窗機制與 Checkpoint](#8-時間視窗機制與-checkpoint)
9. [維護作業參考](#9-維護作業參考)

---

## 1. 管線總覽

Bronze 層資料就緒後，`execute_etl.py` 依 `pipeline_config.yaml` 定義的階段順序，
透過「時間視窗批次」驅動 5 支 SQL 模板，將資料逐步轉換至 Gold 層。

```
Bronze 層 (18 張原始表)
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
        │              (range() 展開活躍日期，7 日滾動 uniqExact)
        │
Stage 6 ▼  backfill_gold.sql
        gold.rmv_l5_task_completion_phys
        (FULL OUTER JOIN 合併 Milestone + ACC)
        │
        ▼
        gold.rmv_l5_task_completion  (VIEW + FINAL)
        (BI/API 查詢入口)
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
    argMaxIf(if(v.LONG_ = 1,'true','false'), v.REV_,
             v.NAME_ = 'autoComplete')                 AS varinst_autoComplete
FROM bronze.bpm_act_hi_varinst v
INNER JOIN target_procs t ON v.PROC_INST_ID_ = t.PROC_INST_ID_
WHERE v.NAME_ IN ('region','plant','factory','lineName','moNumber','autoComplete')
  AND v.CREATE_TIME_ >= parseDateTimeBestEffort('{start_ts}') - INTERVAL 180 DAY
  AND v.CREATE_TIME_ <= '{end_ts}'
GROUP BY v.PROC_INST_ID_
```

**關鍵設計說明**：

- **`argMaxIf`**：取同一屬性中 `REV_` 最大（最新）的值，處理流程變數被更新的情境。
- **`INNER JOIN target_procs`**：只處理本視窗有任務活動的流程實例，大幅縮小掃描量。
- **`INTERVAL 180 DAY`**：流程變數可能在任務開始前 180 天就已寫入（長期流程），故向前延伸查找。

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

將核心事實表的任務生命週期事件，展開為每日快照，計算 Todo / Doing / Done 三種狀態計數。

### 5.2 核心邏輯：ARRAY JOIN 展開

每個任務最多有 3 個時間點（Start / Claim / End），透過 `ARRAY JOIN` 將一列任務展開為最多 3 列快照：

```sql
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayDistinct(arrayFilter(
    d -> d IS NOT NULL,
    [task_start_date, task_claim_date, task_end_date]
)) AS snapshot_date
```

### 5.3 狀態判定公式

快照展開後，在該 `snapshot_date` 時間點上判定任務狀態：

```
Todo  = snapshot_date < COALESCE(task_claim_date, task_end_date, today()+1)
        (尚未被任何人認領)

Doing = task_claim_date IS NOT NULL
        AND snapshot_date >= task_claim_date
        AND (task_end_date IS NULL OR snapshot_date < task_end_date)
        (已認領但尚未完結)

Done  = task_end_date IS NOT NULL
        AND snapshot_date >= task_end_date
        (已完結)
```

### 5.4 輸出欄位

| 欄位          | 說明                        |
| :------------ | :-------------------------- |
| `snapshot_date` | 快照日期（Date）           |
| `vx_type`     | V1 / V2 / V3               |
| `region`      | 區域代碼                    |
| `plant`       | 廠區代碼                    |
| `factory`     | 工廠代碼                    |
| `line`        | 線體代碼                    |
| `total_task`  | 當日該維度下的任務總數       |
| `todo_count`  | 待辦任務數                  |
| `doing_count` | 進行中任務數                |
| `done_count`  | 已完成任務數                |

---

## 6. Stage 5 — ACC 七日滾動去重 (backfill_gold_acc.sql)

### 6.1 目的

計算 7 日滾動視窗內仍處於在途（Todo + Doing）狀態的**唯一**任務數量（ACC, Accumulated）。此指標需跨日去重，運算成本遠高於 Milestone，因此獨立計算。

### 6.2 核心邏輯：range() 展開活躍日期

不同於 Milestone 的事件日期展開，ACC 將每個任務展開為「活躍期間」的連續日期，最多展開 7 天：

```sql
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayMap(
    d -> toDate(d),
    range(
        toUInt32(task_start_date),
        toUInt32(least(
            COALESCE(task_end_date, today() + 2),   -- 未完結則到今天後一天
            task_start_date + 7,                    -- 最多展開 7 天
            toDate('{end_ts}') + 1                  -- 不超過視窗上限
        ))
    )
) AS active_date
WHERE is_excluded = 0
  AND active_date >= toDate('{start_ts}')
  AND active_date <= toDate('{end_ts}')
  AND (task_end_date IS NULL OR task_end_date > active_date)  -- 過濾已完結的日期
```

展開後，使用 `uniqExact` 精確去重：

```sql
SELECT
    active_date AS snapshot_date,
    vx_type, region, plant, factory, line,
    uniqExact(task_id) AS acc_todo_doing
GROUP BY active_date, vx_type, region, plant, factory, line
```

### 6.3 為何使用 range() 而非 JOIN

`range()` 產生日期序列後 `ARRAY JOIN` 展開，在 ClickHouse 的 columnar 引擎下效能遠優於傳統的 Date Range CROSS JOIN，同時避免大量中間表佔用記憶體。

---

## 7. Stage 6 — 最終合併主表 (backfill_gold.sql)

### 7.1 目的

將 Milestone（Todo/Doing/Done）與 ACC（7日在途量）兩個獨立計算結果，透過 `FULL OUTER JOIN` 合併至最終金層主表。

### 7.2 核心邏輯

```sql
INSERT INTO gold.rmv_l5_task_completion_phys
SELECT
    COALESCE(m.snapshot_date, a.snapshot_date) AS snapshot_date,
    COALESCE(m.vx_type,  a.vx_type)  AS vx_type,
    COALESCE(m.region,   a.region)   AS region,
    COALESCE(m.plant,    a.plant)    AS plant,
    COALESCE(m.factory,  a.factory)  AS factory,
    COALESCE(m.line,     a.line)     AS line,
    COALESCE(m.total_task,    0) AS total_task,
    COALESCE(m.todo_count,    0) AS todo_count,
    COALESCE(m.doing_count,   0) AS doing_count,
    COALESCE(m.done_count,    0) AS done_count,
    COALESCE(a.acc_todo_doing, 0) AS acc_todo_doing
FROM (
    SELECT * FROM gold.rmv_l5_milestone_phys FINAL
    WHERE snapshot_date >= toDate('{start_ts}')
      AND snapshot_date <= toDate('{end_ts}')
) m
FULL OUTER JOIN (
    SELECT * FROM gold.rmv_l5_acc_phys FINAL
    WHERE snapshot_date >= toDate('{start_ts}')
      AND snapshot_date <= toDate('{end_ts}')
) a ON m.snapshot_date = a.snapshot_date
   AND m.vx_type = a.vx_type  AND m.region = a.region
   AND m.plant   = a.plant    AND m.factory = a.factory
   AND m.line    = a.line;
```

### 7.3 為何使用 FULL OUTER JOIN

| 情境 | 說明 |
| :--- | :--- |
| 只有 Milestone，無 ACC | 某線體當日有任務快照，但任務均早於 7 日前完結，不計入 ACC |
| 只有 ACC，無 Milestone | 理論上不應發生，但 FULL OUTER JOIN 確保不遺失 |
| 兩者皆有 | 正常情況，直接合併 |

### 7.4 BI 對接視圖

應用層（Cube.js / FastAPI）統一透過視圖讀取，確保 `ReplacingMergeTree` 去重已完成：

```sql
-- 定義於 sql/etl/schema/06_gold_kpi_task_completion.sql
CREATE VIEW gold.rmv_l5_task_completion AS
SELECT * FROM gold.rmv_l5_task_completion_phys FINAL;
```

---

## 8. 時間視窗機制與 Checkpoint

### 8.1 視窗切割方式

`execute_etl.py` 依 `--step-days` 參數將整個日期範圍切割為等長視窗，逐一執行：

```
--start 2025-01-01  --end 2025-12-31  --step-days 10

視窗 1:  2025-01-01 00:00:00  ~  2025-01-10 23:59:59
視窗 2:  2025-01-11 00:00:00  ~  2025-01-20 23:59:59
...
視窗 37: 2025-12-22 00:00:00  ~  2025-12-31 23:59:59

每個視窗 × 5 個 SQL 階段 = 185 次 SQL 執行
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

## 9. 維護作業參考

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
| 完整技術設計文件 | `docs/DMP_Flowable_Technical_Documentation.md` → §3~§6 |

---

**文件負責人**: AIT / Data Engineering  
**審核狀態**: 已對照 `sql/etl/dml/` 下所有 SQL 模板及 `execute_etl.py` 執行邏輯驗證完成
