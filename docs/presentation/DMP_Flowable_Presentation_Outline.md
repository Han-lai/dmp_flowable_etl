# DMP Flowable 技術簡報大綱

**簡報時長**: 15 分鐘
**目標受眾**: 技術團隊 / 資料工程相關人員
**簡報日期**: 2026-04
**版本**: 1.0

---

## 目錄

1. [專案核心重點分析](#1-專案核心重點分析)
2. [簡報敘事邏輯](#2-簡報敘事邏輯)
3. [章節規劃總覽](#3-章節規劃總覽)
4. [各章節詳細內容](#4-各章節詳細內容)
5. [技術實據彙整](#5-技術實據彙整)

---

## 1. 專案核心重點分析

| 面向 | 核心重點 |
|------|----------|
| **業務價值** | 將 Flowable BPM 資料轉化為 L5 任務完成率 KPI，支援管理決策 |
| **技術挑戰** | 在 6GB RAM 受限環境下，實現 100 人併發的穩定查詢 |
| **架構創新** | 三層獎牌架構 + 物理化 Gold 層，將運算從查詢時移至 ETL 批次 |
| **工程實踐** | ODBC 遷移、索引優化、時間視窗運算、斷點續傳 |

---

## 2. 簡報敘事邏輯

```
業務背景 → 技術挑戰 → 架構設計 → 關鍵實作 → 效能成果 → 未來展望
   WHY        WHAT       HOW        DEEP DIVE    PROOF      NEXT
```

**開場 Hook**: 「如何在 6GB RAM 的環境下，支撐 100 人同時查詢 5000 萬筆流程資料？」

**核心訊息**: 透過三層架構 + 物理化 Gold 層，將運算從查詢時移至批次，實現低成本高併發。

**結尾 Takeaway**: 資料工程不只是「搬資料」，而是在限制條件下做出最佳的架構取捨。

---

## 3. 章節規劃總覽

| 章節 | 頁面標題 | 時間 | 技術主題 |
|:----:|----------|:----:|:--------:|
| 1 | 專案總覽 | 1 min | - |
| 2 | 業務需求與痛點 | 1 min | - |
| 3 | Row vs Column：為什麼選 ClickHouse | 1.5 min | 技術 1 |
| 4 | 壓縮效益與效能數據 | 1 min | 技術 1 |
| 5 | 三層獎牌架構總覽 | 1 min | - |
| 6 | ODBC 資料同步機制 | 1.5 min | 技術 2 |
| 7 | Watermark 增量追蹤 | 1 min | 技術 2 |
| 8 | MergeTree 與索引策略 | 1.5 min | 技術 3 |
| 9 | Bronze → Silver → Gold 自動化 | 1.5 min | 技術 4 |
| 10 | ETL 關鍵轉換邏輯 | 1.5 min | 技術 4 |
| 11 | Cube.js 語意層整合 | 1 min | 技術 5 |
| 12 | 週/月報表計算邏輯 | 1 min | 技術 5 |
| 13 | 效能壓測成果 | 1 min | - |
| 14 | 總結與未來規劃 | 0.5 min | - |
| **合計** | **14 頁** | **15 min** | |

---

## 4. 各章節詳細內容

---

### 第 1 頁：專案總覽

**頁面標題**: DMP Flowable 資料倉儲專案

**重點摘要**:
- DMP Flowable 是一套將 Flowable BPM 流程資料同步至 ClickHouse 的資料倉儲系統
- 最終產出 L5 任務完成率等業務 KPI
- 定位為「資料工程 + BI 服務」整合專案

**建議內容**:
```
┌─────────────────────────────────────────────────────┐
│                 DMP Flowable                        │
│         資料倉儲與 BI 分析平台                        │
├─────────────────────────────────────────────────────┤
│  來源: MSSQL Flowable BPM (5000萬+ 筆流程資料)       │
│  目標: ClickHouse 分析型資料庫                       │
│  產出: L5 任務完成率 KPI Dashboard                   │
│  架構: Bronze → Silver → Gold 三層獎牌架構           │
└─────────────────────────────────────────────────────┘
```

**為什麼放這裡**: 開場先建立共識，讓聽眾理解專案的定位與價值。

---

### 第 2 頁：業務需求與痛點

**頁面標題**: 為什麼需要這個專案？

**重點摘要**:
- 業務端需要即時掌握任務完成狀態 (Todo/Doing/Done)
- 來源系統為 MSSQL 交易型資料庫，無法直接支撐 BI 分析查詢
- 需要一套專屬的分析管線

**建議內容**:
```
痛點 1: MSSQL 是 OLTP 資料庫，不適合分析查詢
        → 複雜報表查詢會影響生產系統效能

痛點 2: EAV 格式資料難以直接使用
        → 流程變數儲存為縱向格式，需轉置為寬表

痛點 3: 需支援多維度下鑽分析
        → Region → Plant → Factory → Line 五階維度

痛點 4: 高併發存取需求
        → 100+ 使用者同時查詢報表
```

**為什麼放這裡**: 在介紹解決方案前，先讓聽眾理解「為什麼要做這件事」。

---

### 第 3 頁：Row vs Column - 為什麼選 ClickHouse

**頁面標題**: 列式儲存 vs 行式儲存

**重點摘要**:
- MSSQL (Row Store): 整行讀取，適合 OLTP
- ClickHouse (Column Store): 只讀取所需欄位，適合 OLAP
- 分析查詢效能差異可達數十倍

**建議內容**:

```
┌─ Row Store (MSSQL) ─┐    ┌─ Column Store (ClickHouse) ─┐
│ ID  Name  Dept Sal  │    │ ID │ Name │ Dept │ Salary │
│ 1   Amy   IT   50K  │    │ 1  │ Amy  │ IT   │ 50K    │
│ 2   Bob   HR   45K  │    │ 2  │ Bob  │ HR   │ 45K    │
│ 3   Cat   IT   55K  │    │ 3  │ Cat  │ IT   │ 55K    │
└─────────────────────┘    └────┴──────┴──────┴────────┘

SELECT AVG(Salary) FROM employees WHERE Dept = 'IT'

Row Store:  讀取全部 3 行 × 4 欄 = 12 個值
Column Store: 只讀取 Dept + Salary = 6 個值 ✓
```

**效能對比表**:

| 對比面向 | MSSQL (Row Store) | ClickHouse (Column Store) |
|----------|-------------------|---------------------------|
| 儲存架構 | 行式儲存，整行讀取 | 列式儲存，只讀取所需欄位 |
| 壓縮比 | 約 1:1 ~ 1:2 | **最高 31.93x** |
| 併發效能 | 受限於鎖機制 | **100 併發 100% 成功** |
| 分析查詢 | 秒級以上 | **P99 = 0.61 秒** |

**為什麼放這裡**: 說明技術選型的核心理由。

---

### 第 4 頁：壓縮效益與效能數據

**頁面標題**: ClickHouse 壓縮與效能實測

**重點摘要**:
- LZ4 壓縮 + 列式儲存帶來極高壓縮比
- 大幅降低 I/O 與儲存成本

**專案實測數據**:

| 資料表 | 資料量 | 原始大小 | 壓縮後 | 壓縮比 |
|--------|--------|----------|--------|--------|
| bpm_act_hi_varinst | 1,734 萬筆 | 2.35 GiB | 174.30 MiB | **13.83x** |
| bpm_act_hi_taskinst | 147 萬筆 | 469.33 MiB | 96.20 MiB | **4.88x** |
| bpm_act_hi_identitylink | 123 萬筆 | 4.14 GiB | 132.71 MiB | **31.93x** |

**Gold vs Silver 即時聚合效能對比**:

| 併發數 | Gold 實體表 P99 | Silver 即時聚合 P99 | 效能差距 |
|--------|-----------------|---------------------|----------|
| 10 併發 | 0.163 秒 | 0.629 秒 | Gold 快 **3.9 倍** |
| 50 併發 | 0.616 秒 | 3.411 秒 | Gold 快 **5.5 倍** |
| 100 併發 | 0.391 秒 | 4.450 秒 | Gold 快 **11.4 倍** |

**為什麼放這裡**: 用數據佐證技術選型的正確性。

---

### 第 5 頁：三層獎牌架構總覽

**頁面標題**: Medallion Architecture

**重點摘要**:
- Bronze: 原始資料落地，保留來源全貌
- Silver: 清洗轉換，EAV 轉置、維度整合
- Gold: KPI 物理化，預計算聚合指標

**建議內容**:

```
MSSQL (來源)
    │
    ▼  sync_unified_odbc.py (Native ODBC)
┌─────────────────────────────────────────┐
│  Bronze 層 (18 張表)                    │
│  • BPM 流程核心: 5 表                   │
│  • HR 維度主檔: 6 表                    │
│  • MDM 製造維度: 7 表                   │
│  • ENGINE: ReplacingMergeTree           │
└─────────────────────────────────────────┘
    │
    ▼  execute_etl.py Stage 1-2
┌─────────────────────────────────────────┐
│  Silver 層 (清洗轉換)                   │
│  • mv_varinst_pivoted (EAV → 寬表)      │
│  • mv_fact_task_vx (核心事實表)         │
│  • mv_dim_mfg_five_level (五階維度)     │
└─────────────────────────────────────────┘
    │
    ▼  execute_etl.py Stage 4-6
┌─────────────────────────────────────────┐
│  Gold 層 (KPI 物理化)                   │
│  • rmv_l5_milestone_phys (Todo/Doing/Done) │
│  • rmv_l5_acc_phys (7日滾動 ACC)        │
│  • rmv_l5_task_completion (BI 視圖)     │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  Serving 層                             │
│  • Cube.js (語意層 API)                 │
│  • Superset (BI Dashboard)              │
└─────────────────────────────────────────┘
```

**為什麼放這裡**: 這是專案的核心架構，需要完整說明。

---

### 第 6 頁：ODBC 資料同步機制

**頁面標題**: sync_unified_odbc.py 同步架構

**重點摘要**:
- 使用 Native ODBC Driver 取代 JDBC Bridge
- 支援批次增量 (batch) 與全量 (full) 兩種策略
- Adaptive Batching: OOM 時自動對半切分

**同步流程**:

```python
# 核心流程 (sync_unified_odbc.py)

1. 建立 ODBC Table Engine
   ┌────────────────────────────────────────────────┐
   │ CREATE TABLE odbc_temp_xxx (...)               │
   │ ENGINE = ODBC('DSN=MSSQL_DSN;Database=...')    │
   └────────────────────────────────────────────────┘
   → 繞過 MS-ODBC 動態 Schema 探測導致的死鎖問題

2. 批次增量同步 (大表)
   ┌────────────────────────────────────────────────┐
   │ • 依 time_col 分批 (預設 10 天/批)              │
   │ • Watermark 追蹤上次同步位置                    │
   │ • OOM 時自動對半切分 (Adaptive Batching)        │
   └────────────────────────────────────────────────┘

3. 全量同步 (維度表)
   ┌────────────────────────────────────────────────┐
   │ TRUNCATE → INSERT (確保 1:1 一致)              │
   └────────────────────────────────────────────────┘
```

**同步策略配置** (sync_tables.yaml):

```yaml
# 增量同步 (大表)
taskinst:
  source: "APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108"
  target: "bronze.bpm_act_hi_taskinst"
  strategy: "batch"
  time_col: "LAST_UPDATED_TIME_"
  step_days: 10

# 全量同步 (維度表)
hr_employee:
  source: "APP_SRV_COMMON.dbo.HR_Employee_0202"
  target: "bronze.common_hr_employee"
  strategy: "full"
```

**為什麼放這裡**: 說明資料如何從來源進入系統。

---

### 第 7 頁：Watermark 增量追蹤

**頁面標題**: 增量同步與斷點續傳

**重點摘要**:
- Watermark 表記錄每張表的同步進度
- 支援斷點續傳，失敗後可從上次位置繼續
- 累計統計同步筆數與耗時

**Watermark 機制**:

```sql
-- bronze._sync_watermark 表結構
CREATE TABLE bronze._sync_watermark (
    table_name String,           -- 表名
    last_sync_time DateTime64(3),-- 資料時間戳 (同步到哪裡)
    sync_time DateTime64(3),     -- 執行時間 (何時同步)
    row_count UInt64,            -- 累計筆數
    duration_ms Float64          -- 累計耗時
) ENGINE = ReplacingMergeTree(sync_time)
ORDER BY (table_name)
```

**增量同步流程圖**:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  查詢       │     │  同步       │     │  更新       │
│  Watermark  │ ──▶ │  新資料     │ ──▶ │  Watermark  │
│  上次位置   │     │  (增量)     │     │  新位置     │
└─────────────┘     └─────────────┘     └─────────────┘

例: taskinst 表
  上次同步: 2026-04-01 00:00:00
  本次同步: 2026-04-01 ~ 2026-04-10 (10天增量)
  更新位置: 2026-04-10 23:59:59
```

**18 張同步表清單**:

| 類別 | 表數量 | 同步策略 | 說明 |
|------|--------|----------|------|
| BPM 流程核心 | 5 表 | batch | taskinst, varinst, procinst, identitylink, procdef |
| HR 維度 | 6 表 | full | employee, emp_node_role, emp_org_info... |
| MDM 製造維度 | 7 表 | full | line_desc, prod_area, factory_area... |

**為什麼放這裡**: 補充同步機制的追蹤與容錯設計。

---

### 第 8 頁：MergeTree 與索引策略

**頁面標題**: ClickHouse 表結構優化

**重點摘要**:
- ORDER BY: 決定資料排序，優化範圍查詢與 JOIN
- Skip Index: minmax / bloom_filter 跳過不相關資料塊
- ReplacingMergeTree: 支援批次寫入相同主鍵，自動去重

**Bronze 層核心表配置**:

```sql
-- taskinst 表: 優化 PROC_INST_ID_ JOIN 查詢
CREATE TABLE bronze.bpm_act_hi_taskinst (
    ID_ String,
    PROC_INST_ID_ Nullable(String),
    START_TIME_ DateTime64(3),
    ...
    -- Skip Index: 時間範圍查詢優化
    INDEX idx_start_time START_TIME_ TYPE minmax GRANULARITY 3,
    INDEX idx_claim_time CLAIM_TIME_ TYPE minmax GRANULARITY 3,
    INDEX idx_end_time END_TIME_ TYPE minmax GRANULARITY 3
)
ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (PROC_INST_ID_, ID_);  -- JOIN 優化

-- varinst 表: 優化 TASK_ID_ IN 查詢
CREATE TABLE bronze.bpm_act_hi_varinst (
    PROC_INST_ID_ String,
    TASK_ID_ Nullable(String),
    ...
    -- Bloom Filter: IN 查詢優化
    INDEX idx_task_id TASK_ID_ TYPE bloom_filter GRANULARITY 3
)
ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (PROC_INST_ID_, NAME_, CREATE_TIME_);
```

**索引效能提升**:

| 表名 | ORDER BY | Skip Index | 效能提升 |
|------|----------|------------|----------|
| taskinst | (PROC_INST_ID_, ID_) | START_TIME_ (minmax) | JOIN **68x** |
| varinst | (PROC_INST_ID_, NAME_, CREATE_TIME_) | TASK_ID_ (bloom_filter) | IN **10x-50x** |

**ReplacingMergeTree 機制**:

```sql
-- 寫入時: 允許重複主鍵
INSERT INTO table VALUES (1, 'v1', 1), (1, 'v2', 2)

-- 讀取時: 使用 FINAL 取得最新版本
SELECT * FROM table FINAL
→ 只返回 (1, 'v2', 2)
```

**為什麼放這裡**: 說明 ClickHouse 特有的效能優化機制。

---

### 第 9 頁：Bronze → Silver → Gold 自動化

**頁面標題**: execute_etl.py 自動化管線

**重點摘要**:
- 6 階段轉換流程，由 YAML 設定驅動
- 時間視窗批次處理，適應低記憶體環境
- Checkpoint 斷點續傳

**ETL Pipeline 配置** (pipeline_config.yaml):

```yaml
pipeline_stages:
  - name: "Stage 1: Dimension Pivot"
    steps:
      - phase_id: "silver_varinst_pivoted"
        template: "backfill_pivot.sql"      # EAV → 寬表

  - name: "Stage 2: Fact & Gold Aggregation"
    steps:
      - phase_id: "silver_facts"
        template: "backfill_silver.sql"     # 核心事實表
      - phase_id: "silver_exclusion"
        template: "backfill_exclusion.sql"  # 排除標記
      - phase_id: "gold_milestone"
        template: "backfill_gold_milestone.sql"  # Todo/Doing/Done
      - phase_id: "gold_acc"
        template: "backfill_gold_acc.sql"   # 7日滾動 ACC
      - phase_id: "gold_unified"
        template: "backfill_gold.sql"       # 最終合併
```

**6 階段流程圖**:

```
┌──────────────────────────────────────────────────────────────────┐
│ Stage 1: EAV Pivot                                               │
│ ┌─────────────────┐     ┌─────────────────────────────────────┐  │
│ │ bpm_act_hi_     │ ──▶ │ silver.mv_varinst_pivoted           │  │
│ │ varinst (EAV)   │     │ (region, plant, factory, line...)   │  │
│ └─────────────────┘     └─────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Stage 2: Silver Facts                                            │
│ ┌─────────────────┐     ┌─────────────────────────────────────┐  │
│ │ taskinst +      │ ──▶ │ silver.mv_fact_task_vx              │  │
│ │ pivoted + MDM   │     │ (task_status, vx_type, 五階維度)     │  │
│ └─────────────────┘     └─────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Stage 4-6: Gold Aggregation                                      │
│ ┌─────────────────┐     ┌─────────────────────────────────────┐  │
│ │ mv_fact_task_vx │ ──▶ │ gold.rmv_l5_milestone_phys          │  │
│ │                 │     │ gold.rmv_l5_acc_phys                │  │
│ │                 │     │ gold.rmv_l5_task_completion_phys    │  │
│ └─────────────────┘     └─────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**為什麼放這裡**: 展示完整的資料轉換自動化流程。

---

### 第 10 頁：ETL 關鍵轉換邏輯

**頁面標題**: Silver/Gold 層核心 SQL 邏輯

**重點摘要**:
- EAV Pivot: 縱向變數轉橫向欄位
- VTYPE 分類: 工單號優先規則
- ARRAY JOIN: 展開日期快照

**1. EAV Pivot** (backfill_pivot.sql):

```sql
-- 將縱向變數轉為橫向欄位
SELECT
    PROC_INST_ID_,
    argMaxIf(TEXT_, REV_, NAME_ = 'region') AS varinst_region,
    argMaxIf(TEXT_, REV_, NAME_ = 'plant') AS varinst_plant,
    argMaxIf(TEXT_, REV_, NAME_ = 'factory') AS varinst_factory,
    argMaxIf(TEXT_, REV_, NAME_ = 'lineName') AS varinst_lineName,
    argMaxIf(TEXT_, REV_, NAME_ = 'moNumber') AS varinst_moNumber
FROM bronze.bpm_act_hi_varinst
GROUP BY PROC_INST_ID_
```

**2. VTYPE 分類規則** (backfill_silver.sql):

```sql
CASE
    -- 規則 1: 特定工單號 → V1 (優先)
    WHEN substring(moNumber, 1, 3) IN ('196','199','200','210','212','213')
    THEN 'V1'
    -- 規則 2-4: TASK_DEF_KEY_ 前綴匹配
    WHEN TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
    WHEN TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
    WHEN TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
    -- 規則 5: 預設
    ELSE 'Unknown'
END AS vx_type
```

**3. Gold 里程碑 ARRAY JOIN** (backfill_gold_milestone.sql):

```sql
-- 使用 ARRAY JOIN 展開每個任務的關鍵日期為多個快照
SELECT snapshot_date, vx_type, region, plant, factory, line,
       countIf(...) AS todo_count,
       countIf(...) AS doing_count,
       countIf(...) AS done_count
FROM silver.mv_fact_task_vx
ARRAY JOIN arrayDistinct([task_start_date, task_claim_date, task_end_date])
    AS snapshot_date
GROUP BY snapshot_date, vx_type, region, plant, factory, line
```

**4. 7 日滾動 ACC** (backfill_gold_acc.sql):

```sql
-- 使用 range() 展開任務的 7 天活躍期
ARRAY JOIN arrayMap(d -> toDate(d),
    range(task_start_date, task_start_date + 7)
) AS active_date
-- uniqExact 跨日去重
SELECT active_date, uniqExact(task_id) AS acc_todo_doing
```

**為什麼放這裡**: 深入展示轉換邏輯的技術細節。

---

### 第 11 頁：Cube.js 語意層整合

**頁面標題**: Cube.js 語意層架構

**重點摘要**:
- Cube.js 作為 ClickHouse 與 Superset 之間的語意層
- 提供 Dimensions (維度) 與 Measures (指標) 的統一定義
- 支援 Time Machine 回溯查詢

**架構圖**:

```
┌─────────────────────────────────────────────────────────────┐
│                     Superset Dashboard                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ 月報表  │ │ 週報表  │ │ 日報表  │ │ 趨勢圖  │           │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │
└───────┼──────────┼──────────┼──────────┼───────────────────┘
        │          │          │          │
        └──────────┴──────────┴──────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Cube.js 語意層                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ L5TaskPeriodic Cube                                  │   │
│  │ ├─ Measures: totalQty, todoQty, doneRate, accRate   │   │
│  │ └─ Dimensions: region, plant, factory, line, vxType │   │
│  └─────────────────────────────────────────────────────┘   │
│  • 查詢快取                                                 │
│  • Pre-aggregation                                         │
│  • Time Machine 邏輯                                       │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              ClickHouse Gold Layer                          │
│              gold.rmv_l5_task_completion                    │
└─────────────────────────────────────────────────────────────┘
```

**Cube.js 模型定義** (cube_l5_task_periodic.js):

```javascript
cube(`L5TaskPeriodic`, {
    sql: `SELECT * FROM gold.rmv_l5_task_completion`,

    measures: {
        totalQty: { type: `sum`, sql: `total_task` },
        todoQty: { type: `sum`, sql: `todo_count` },
        doneRate: {
            type: `number`,
            sql: `round(sum(done_count) * 100.0 / nullIf(sum(total_task), 0), 2)`
        },
        accRate: {
            type: `number`,
            sql: `round(sum(acc_todo_doing) * 100.0 / nullIf(sum(acc_total), 0), 2)`
        }
    },

    dimensions: {
        diffRegion: { type: `string`, sql: `region`, title: '地區' },
        diffPlant: { type: `string`, sql: `plant`, title: '廠區' },
        diffFactory: { type: `string`, sql: `factory`, title: '工廠' },
        diffLine: { type: `string`, sql: `line`, title: '線體' },
        diffVxType: { type: `string`, sql: `vx_type`, title: 'Vx 類型' }
    }
});
```

**為什麼放這裡**: 說明展示層如何與資料層對接。

---

### 第 12 頁：週/月報表計算邏輯

**頁面標題**: Time Machine 與週期性報表

**重點摘要**:
- 支援 Month / Week / Day 三種時間粒度
- Time Machine: 可回溯查詢歷史快照
- 7 日滾動 ACC: 使用視窗函數計算

**三段時間粒度計算**:

```sql
-- A. Month: 月度加總，ACC 取月底快照
SELECT 'Month' as granularity,
       formatDateTime(anchor_dt, '%b.') as period_name,
       sum(total_task), sum(todo_count), sum(doing_count), sum(done_count),
       argMax(acc_todo_doing, snapshot_date) as acc_qty  -- 月底快照
FROM base
WHERE snapshot_date >= toStartOfMonth(anchor_dt)
  AND snapshot_date <= anchor_dt
GROUP BY ...

-- B. Week: ISO 週加總
SELECT 'Week' as granularity,
       concat('W', toString(toWeek(snapshot_date, 1))) as period_name,
       ...
WHERE toWeek(snapshot_date, 1) = toWeek(anchor_dt, 1)

-- C. Day: 7 日滾動視窗
SELECT 'Day' as granularity,
       toString(snapshot_date) as period_name,
       sum(total_qty) OVER (
           PARTITION BY vx_type, region, plant, factory, line
           ORDER BY snapshot_date
           ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
       ) as acc_total_qty
```

**Time Machine 機制**:

```
用戶選擇日期: 2026-04-10
         │
         ▼
┌─────────────────────────────────────────┐
│ calc_anchor:                            │
│   anchor_dt = min(選擇日期, today())    │
│                                         │
│ base 資料範圍:                          │
│   toStartOfMonth(anchor_dt) - 1 MONTH   │
│   ~ toLastDayOfMonth(anchor_dt) + 1 MONTH│
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 輸出:                                   │
│   Month: Apr. (4月累計)                 │
│   Week: W15 (當週), W14 (上週), W13     │
│   Day: 04-10, 04-09, ..., 04-04 (7天)  │
└─────────────────────────────────────────┘
```

**為什麼放這裡**: 展示報表計算的業務邏輯實現。

---

### 第 13 頁：效能壓測成果

**頁面標題**: 100 併發壓測驗證

**重點摘要**:
- QPS 提升 8 倍以上
- Peak RAM 降低 98%
- P99 延遲穩定在 1 秒內

**架構轉換前後對比**:

| 指標 | Before (動態視圖) | After (物理化 Gold) | 改善幅度 |
|------|-------------------|---------------------|----------|
| **QPS** | 10.5 ~ 12.4 | **84.58** | **+8.05 倍** |
| **Peak RAM** | 404.10 MiB | **< 5 MiB** | **-98%** |
| **P99 Latency** | 1.34 秒 | **0.61 秒** | **-54%** |
| **可用性** | >50併發 OOM | **100併發 100%** | **穩定** |

**併發壓測結果**:

| 併發數 | 狀態 | QPS | P50 | P95 | P99 |
|--------|------|-----|-----|-----|-----|
| 10 併發 | PASS | 49.09 | 0.090s | 0.154s | 0.163s |
| 20 併發 | PASS | 88.43 | 0.199s | 0.271s | 0.306s |
| 50 併發 | PASS | 84.58 | 0.396s | 0.543s | 0.616s |
| 100 併發 | PASS | 78.66 | 0.262s | 0.373s | 0.391s |

**資源消耗**:

| 資源指標 | 實測數值 | 佔用率 |
|----------|----------|--------|
| 平均 RAM | 3.84 ~ 3.99 MiB | 0.034% |
| 峰值 RAM | 4.38 ~ 4.97 MiB | 0.044% |
| CPU 單次 | 68 ~ 71 ms | 微秒級 |

**為什麼放這裡**: 用數據證明架構設計的有效性。

---

### 第 14 頁：總結與未來規劃

**頁面標題**: Summary & Next Steps

**重點摘要**:
- 專案已穩定運作於生產環境
- 關鍵技術突破總結
- 未來優化方向

**關鍵成就**:

```
✅ ODBC 遷移完成
   → 解決 JDBC Bridge OOM 問題

✅ 物理化 Gold 層
   → 100 併發壓測通過

✅ 索引優化
   → JOIN 效能提升 68x

✅ 自動化 ETL
   → 斷點續傳、低記憶體模式

✅ Cube.js 整合
   → 週/月報表 Time Machine
```

**未來規劃**:

| 項目 | 說明 | 優先級 |
|------|------|--------|
| Gold 層效能調查 | 調查資料量減少但查詢變慢的原因 | 高 |
| L7 人員使用率 | 啟用 User Utilization 指標 | 中 |
| 監控告警 | 建立 ETL 失敗自動告警 | 中 |
| 文件維護 | 保持技術文件與程式碼同步 | 低 |

**結語**:

> 「資料工程不只是『搬資料』，而是在限制條件下做出最佳的架構取捨。」

**為什麼放這裡**: 收尾總結，給聽眾 takeaway 並預告後續。

---

## 5. 技術實據彙整

### 5.1 專案檔案對照表

| 技術主題 | 相關檔案 | 路徑 |
|----------|----------|------|
| Row vs Column | 效能報告 | `docs/05_monitoring/Physical_Gold_Benchmark_Report.md` |
| ODBC 同步 | 同步腳本 | `scripts/etl/sync_unified_odbc.py` |
| 同步配置 | YAML | `scripts/etl/config/sync_tables.yaml` |
| MergeTree 索引 | DDL | `sql/etl/schema/01_bronze_flowable_core.sql` |
| ETL 管線 | 執行腳本 | `scripts/etl/execute_etl.py` |
| Pipeline 配置 | YAML | `scripts/etl/config/pipeline_config.yaml` |
| Silver 轉換 | SQL | `sql/etl/dml/backfill_silver.sql` |
| Gold 里程碑 | SQL | `sql/etl/dml/backfill_gold_milestone.sql` |
| Gold ACC | SQL | `sql/etl/dml/backfill_gold_acc.sql` |
| Cube.js | 模型 | `cube/model/cubes/cube_l5_task_periodic.js` |
| Cube.js Pivot | 模型 | `cube/model/cubes/cube_l5_task_periodic_pivot.js` |

### 5.2 關鍵數據摘要

```
資料規模:
  • Bronze 層: 5000+ 萬筆
  • taskinst: 147 萬筆
  • varinst: 1,734 萬筆
  • identitylink: 123 萬筆

壓縮效益:
  • 最高壓縮比: 31.93x (identitylink)
  • 平均壓縮比: 10x+

效能提升:
  • QPS: 10.5 → 84.58 (+8x)
  • RAM: 404 MiB → 5 MiB (-98%)
  • P99: 1.34s → 0.61s (-54%)
  • JOIN: 68x 加速
  • IN: 10x-50x 加速

併發能力:
  • 100 併發 100% 成功
  • 佇列防禦機制生效
```

---

## 附錄：簡報製作建議

### 視覺風格
- 使用深色背景 + 亮色文字 (技術風格)
- 程式碼使用等寬字體 (Consolas / Fira Code)
- 架構圖使用一致的配色方案

### 圖表建議
1. **第 3 頁**: Row vs Column 讀取方式對比圖
2. **第 4 頁**: 壓縮比柱狀圖
3. **第 5 頁**: 三層架構流程圖
4. **第 6-7 頁**: 同步流程時序圖
5. **第 8 頁**: ORDER BY 排序示意圖
6. **第 9 頁**: 6 階段 ETL 流程圖
7. **第 13 頁**: 效能對比柱狀圖 + 折線圖

### 演講技巧
- 每頁停留約 1 分鐘
- 技術細節頁可準備 backup slides
- 準備 2-3 個常見 Q&A

---

*文件產生日期: 2026-04-16*
*維護單位: AIT / Data Engineering*
