# 目前架構路徑盤點

> 盤點日期: 2026-01-16
> 專案: DMP Flowable 資料同步

---

## 1) 架構總覽

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    Source                                           │
│                                                                                     │
│   MSSQL (APP_SRV_BPM + APP_SRV_COMMON)                                             │
│   ├── ACT_HI_PROCINST (流程實例)                                                    │
│   ├── ACT_HI_TASKINST (任務實例)                                                    │
│   ├── ACT_HI_VARINST (流程變數)                                                     │
│   ├── ACT_RE_PROCDEF (流程定義)                                                     │
│   ├── FlowableTaskStats (任務統計)                                                  │
│   └── HR_Employee (員工資料)                                                        │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ JDBC Bridge
                                         │ (sync/sync_incremental.py)
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Bronze Layer (ClickHouse)                              │
│                                                                                     │
│   bronze.bpm_act_hi_procinst         (ReplacingMergeTree, 增量)                     │
│   bronze.bpm_act_hi_taskinst         (ReplacingMergeTree, 增量)                     │
│   bronze.bpm_act_hi_varinst          (ReplacingMergeTree, 增量)                     │
│   bronze.bpm_act_re_procdef          (MergeTree, 全量)                              │
│   bronze.common_flowable_task_stats  (ReplacingMergeTree, 增量) ← L5 主要來源       │
│   bronze.common_hr_employee          (MergeTree, 全量)                              │
│   + 10 張其他表                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
          ┌──────────────────────────────┼──────────────────────────────┐
          │                              │                              │
          ▼                              ▼                              ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│  Silver View (即時)      │  │  Silver RMV (效能)       │  │  Silver Table (L5)      │
│                         │  │                         │  │                         │
│  V_PROC_VARIABLES_*     │  │  RMV_PROC_VARIABLES_*   │  │  FACT_TASK_VX_          │
│  V_HI_PROC_TASK_NODE    │  │  RMV_HI_PROC_TASK_NODE  │  │    ATTRIBUTION          │
│  V_HI_PROCINST_NODE     │  │  RMV_HI_PROCINST_NODE   │  │  DIM_CONFIG_USER        │
│  V_HI_BIZ_EVENT_INFO    │  │  RMV_HI_BIZ_EVENT_INFO  │  │  task_detail_wide       │
│                         │  │                         │  │  varinst_*_pivot        │
│  (即時計算)              │  │  (每日 02:00 UTC)        │  │  (手動轉換)              │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
          │                              │                              │
          │                              │                              │
          │         ┌────────────────────┤                              │
          │         │                    │                              │
          │         ▼                    ▼                              ▼
          │   ┌─────────────────────────────────────┐  ┌─────────────────────────────┐
          │   │     Gold Layer (通用指標快照)        │  │  Gold Layer (L5 指標快照)    │
          │   │                                     │  │                             │
          │   │  gold.DAILY_METRICS_SNAPSHOT        │  │  gold.DAILY_L5_TASK_        │
          │   │  gold.DAILY_BIZ_EVENT_SNAPSHOT      │  │    COMPLETION_SNAPSHOT      │
          │   │                                     │  │  gold.DAILY_USER_           │
          │   │  (scripts/create_gold_snapshot.py)  │  │    UTILIZATION_SNAPSHOT     │
          │   └─────────────────────────────────────┘  │                             │
          │                    │                       │  (scripts/create_gold_      │
          │                    │                       │   generic_metrics_snapshot) │
          │                    │                       └─────────────────────────────┘
          │                    │                                       │
          └────────────────────┼───────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Cube.js (語意層)                                        │
│                                                                                     │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────────────┐ │
│  │   Silver Cubes (即時)        │    │   Gold Cubes (歷史趨勢)                      │ │
│  │                             │    │                                             │ │
│  │   ProcTaskNode              │    │   DailyMetricsSnapshot                      │ │
│  │   ProcInstNode              │    │   DailyBizEventSnapshot                     │ │
│  │   BizEventInfo              │    │   DailyL5TaskCompletion (待建)               │ │
│  └─────────────────────────────┘    └─────────────────────────────────────────────┘ │
│                                                                                     │
│  REST API: http://localhost:4002                                                    │
│  Playground: http://localhost:4003                                                  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │     前端/BI      │
                              └─────────────────┘
```

---

## 2) 主要路徑清單

### Path A: Bronze 增量同步路徑

| 項目 | 說明 |
|------|------|
| **目的** | 將 MSSQL 資料同步到 ClickHouse Bronze 層 |
| **觸發方式** | 手動執行 `python sync/sync_incremental.py all` |
| **刷新策略** | 大表增量 (5 張) + 小表全量 (11 張) |
| **使用工具** | JDBC Bridge, Python Script, ClickHouse |
| **工具角色** | JDBC Bridge: 跨資料庫查詢<br>Python Script: 排程控制、Watermark 管理<br>ClickHouse: 資料儲存 (ReplacingMergeTree 去重) |
| **產出物** | Bronze 層 16 張表 |
| **適用情境** | 日常資料同步 |
| **限制** | 無自動排程，需手動執行或外部排程 |

### Path B: Silver 即時查詢路徑

| 項目 | 說明 |
|------|------|
| **目的** | 提供即時、最新的指標查詢 |
| **觸發方式** | 查詢時即時計算 |
| **刷新策略** | 無刷新，每次查詢即時計算 |
| **使用工具** | ClickHouse View, Cube.js |
| **工具角色** | View (V_*): 即時 JOIN 和轉換<br>Cube.js: 語意層封裝 |
| **產出物** | 4 張 Silver View → 3 個 Cube (ProcTaskNode, ProcInstNode, BizEventInfo) |
| **適用情境** | 需要最新資料的即時查詢 |
| **限制** | 效能較慢 (每次重算)，不適合大量報表查詢 |

### Path C: Silver RMV 報表路徑

| 項目 | 說明 |
|------|------|
| **目的** | 提供高效能的報表查詢 |
| **觸發方式** | ClickHouse 自動排程 (REFRESH EVERY 1 DAY) |
| **刷新策略** | 每日全量刷新 (02:00 UTC) |
| **使用工具** | ClickHouse RMV, Cube.js |
| **工具角色** | RMV (RMV_*): 預計算物化視圖<br>Cube.js: 語意層封裝 |
| **產出物** | 4 張 Silver RMV → 3 個 Cube |
| **適用情境** | 報表查詢、Dashboard |
| **限制** | 資料最多延遲 24 小時 |

### Path D: Gold 歷史快照路徑

| 項目 | 說明 |
|------|------|
| **目的** | 提供歷史趨勢查詢和指標回溯 |
| **觸發方式** | 手動執行 `python scripts/create_gold_snapshot.py` |
| **刷新策略** | 每日快照 (設計為 10:00 Asia/Taipei) |
| **使用工具** | Python Script, ClickHouse, Cube.js |
| **工具角色** | Python Script: 快照計算和寫入<br>ClickHouse: 快照儲存 (ReplacingMergeTree)<br>Cube.js: 歷史趨勢 API |
| **產出物** | 2 張 Gold 表 → 2 個 Cube → 2 個 View |
| **適用情境** | 歷史趨勢分析、指標回溯、月報 |
| **限制** | 無自動排程，需手動執行或外部排程；只有執行過的日期才有資料 |

### Path E: L5 任務執行完成率路徑

| 項目 | 說明 |
|------|------|
| **目的** | 提供 L5 任務執行完成率指標（依 Vx/Plant/Factory/Line 維度） |
| **觸發方式** | 手動執行 `python scripts/transform_silver_generic_metrics.py` + `python scripts/create_gold_generic_metrics_snapshot.py` |
| **刷新策略** | 每日全量轉換 + 快照 |
| **使用工具** | Python Script, ClickHouse |
| **工具角色** | Python Script: Silver 轉換 + Gold 快照<br>ClickHouse: 資料儲存 |
| **產出物** | Silver: `FACT_TASK_VX_ATTRIBUTION`, `DIM_CONFIG_USER`<br>Gold: `DAILY_L5_TASK_COMPLETION_SNAPSHOT`, `DAILY_USER_UTILIZATION_SNAPSHOT` |
| **適用情境** | L5 任務執行完成率報表、人員使用率報表 |
| **限制** | 無自動排程；依賴 `bronze.common_flowable_task_stats` |

**L5 資料流：**
```
Bronze                          Silver                              Gold
─────────────────────────────────────────────────────────────────────────────
common_flowable_task_stats  →   FACT_TASK_VX_ATTRIBUTION    →   DAILY_L5_TASK_
bpm_act_hi_procinst         →   (預計算 Vx 歸屬、排除標記)       COMPLETION_SNAPSHOT
bpm_act_hi_varinst          →                                   (按維度+時間區間聚合)
                                DIM_CONFIG_USER             →   DAILY_USER_
                                (Config Users 維度表)            UTILIZATION_SNAPSHOT
```

---

## 3) 路徑對照表

| 路徑 | 觸發方式 | 刷新策略 | 主要工具 | 主要輸出層 | 主要風險/限制 |
|------|----------|----------|----------|------------|---------------|
| **Path A** Bronze 同步 | manual | incremental + full | JDBC Bridge, Python | Bronze | 無自動排程 |
| **Path B** Silver 即時 | on-query | 即時計算 | ClickHouse View, Cube.js | Silver View → Cube | 效能較慢 |
| **Path C** Silver RMV | schedule (daily) | full refresh | ClickHouse RMV, Cube.js | Silver RMV → Cube | 資料延遲 ≤24h |
| **Path D** Gold 快照 | manual | daily snapshot | Python, ClickHouse, Cube.js | Gold → Cube → View | 無自動排程 |
| **Path E** L5 指標 | manual | daily transform + snapshot | Python, ClickHouse | Silver Table → Gold | 無自動排程 |

---

## 4) 工具與功能地圖

| 工具/技術 | 功能定位 | 出現在哪些路徑 | 備註 |
|-----------|----------|----------------|------|
| **MSSQL** | 資料來源 | Path A | APP_SRV_BPM + APP_SRV_COMMON |
| **JDBC Bridge** | 跨資料庫查詢 | Path A | ClickHouse 內建功能 |
| **Python Script** | 排程控制、ETL 邏輯 | Path A, D, E | sync_incremental.py, create_gold_snapshot.py, transform_silver_generic_metrics.py |
| **ClickHouse** | 資料倉儲 | 全部 | Bronze/Silver/Gold 層儲存 |
| **ClickHouse View** | 即時轉換 | Path B | V_* 系列 |
| **ClickHouse RMV** | 預計算物化視圖 | Path C | RMV_* 系列，每日自動刷新 |
| **ClickHouse Table** | 資料儲存 | Path A, D, E | Bronze 表、Silver 事實表、Gold 快照表 |
| **Cube.js** | 語意層、API 封裝 | Path B, C, D | 不負責排程/落地 |
| **Cube.js View** | API 簡化介面 | Path D | HistoricalTrends, HistoricalBizEvents |

---

## 5) 目前架構的「關鍵分歧點」

### 5.1 即時 vs 效能：View 與 RMV 並存

**原因**：同時需要「最新資料」和「高效能查詢」兩種場景
- View (V_*): 即時計算，資料最新，但效能慢 (147ms vs 15ms)
- RMV (RMV_*): 預計算，效能快 4-10 倍，但資料延遲最多 24 小時

**目前狀態**：Cube.js 預設讀取 RMV，需要即時資料時可改用 View

### 5.2 即時指標 vs 歷史趨勢：Silver 與 Gold 並存

**原因**：同時需要「當下狀態」和「歷史回溯」兩種需求
- Silver RMV: 提供當下的指標值（在途任務數、自動完成率）
- Gold 快照: 提供歷史趨勢（本週 vs 上週、月度趨勢）

**目前狀態**：Gold 快照層已建立，但需手動執行，尚無自動排程

### 5.3 Cube.js 是語意層，不是 ETL 工具

**原因**：Cube.js 設計定位是「查詢語意層」，不負責資料落地
- Cube.js 不能原生執行排程寫入
- Cube.js 不能直接 INSERT INTO ClickHouse

**目前狀態**：Gold 快照由 Python Script 執行，Cube.js 只負責讀取和 API 封裝

### 5.4 增量同步 vs 全量同步：混合策略

**原因**：大表全量同步太慢，小表增量同步太複雜
- 大表 (5 張): 增量同步，用 Watermark 追蹤
- 小表 (11 張): 全量同步，DROP + CREATE

**目前狀態**：混合策略已實作，增量同步約 10 秒 vs 全量 68 秒

### 5.5 排程尚未自動化

**原因**：目前處於 MVP 階段，排程機制尚未建立
- Bronze 同步: 手動執行
- Gold 快照: 手動執行
- RMV 刷新: ClickHouse 自動 (唯一自動化的部分)

**目前狀態**：需要外部排程工具 (cron / Windows Task Scheduler / Airflow) 來自動化

---

## 附錄：資料層級對照

| 層級 | 物件類型 | 數量 | 刷新方式 | 用途 |
|------|----------|------|----------|------|
| Bronze | Table | 16 | 手動同步 | 原始資料 |
| Silver | View | 4 | 即時計算 | 即時查詢 |
| Silver | RMV | 4 | 每日自動 | 報表查詢 |
| Silver | Table | 4 | 手動轉換 | L5/人員使用率 |
| Gold | Table | 4 | 手動快照 | 歷史趨勢 |
| Cube.js | Cube | 5 | N/A | 語意封裝 |
| Cube.js | View | 2 | N/A | API 簡化 |

---

## 6) L5 任務執行完成率 - 資料流架構

### 6.1 資料流總覽

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Bronze Layer (來源)                                     │
│                                                                                     │
│   bronze.common_flowable_task_stats    ← 任務統計（含 TaskStatus, TaskBypass）       │
│   bronze.bpm_act_hi_procinst           ← 流程實例（含 BUSINESS_KEY_）                │
│   bronze.bpm_act_hi_varinst            ← 流程變數（含 moNumber）                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ scripts/transform_silver_generic_metrics.py
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Silver Layer (轉換)                                     │
│                                                                                     │
│   silver.FACT_TASK_VX_ATTRIBUTION      ← 任務 Vx 歸屬事實表                          │
│   ├── vx_type (V1/V2/V3)               ← 預計算 Vx 歸屬                              │
│   ├── vx_subtype (V1_NPE/V1_MFG)       ← 預計算 V1 子類型                            │
│   ├── is_excluded (0/1)                ← 預計算排除標記                              │
│   └── is_special_v1_rule (0/1)         ← 是否套用特殊 V1 規則                        │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ scripts/create_gold_generic_metrics_snapshot.py
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Gold Layer (快照)                                       │
│                                                                                     │
│   gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT                                            │
│   ├── 維度: vx_type, vx_subtype, plant, factory, line                               │
│   ├── 時間區間: month/week/day                                                       │
│   └── 指標: total_task_qty, todo_qty, doing_qty, done_qty, todo_pct, ...            │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 計算邏輯詳解

#### 6.2.1 Vx 歸屬判斷

| 規則 | 條件 | 歸屬 |
|------|------|------|
| **特殊 V1 規則** | `moNumber` 開頭為 196/199/200/210/212/213/315 | V1 |
| **一般規則** | `task_definition_key` 前兩字元 | V1/V2/V3/... |

**V1 子類型判斷：**
- `V1_NPE`: 套用特殊 V1 規則 + `BUSINESS_KEY_ LIKE '%NPE%'`
- `V1_MFG`: 套用特殊 V1 規則 + `BUSINESS_KEY_ NOT LIKE '%NPE%'`

**moNumber 來源：**
```sql
-- 從 varinst 轉置取得（EAV 結構）
SELECT PROC_INST_ID_, MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
FROM bronze.bpm_act_hi_varinst
WHERE NAME_ = 'moNumber'
GROUP BY PROC_INST_ID_
```

#### 6.2.2 排除規則

| 排除條件 | 排除原因 |
|---------|---------|
| `task_bypass != 'N'` | bypass |
| `task_definition_key LIKE 'E%'` | E_prefix |
| `task_definition_key LIKE 'C%'` | C_prefix |
| `moNumber LIKE 'Q%'` | Q_order |
| `moNumber LIKE 'R%'` | R_order |

#### 6.2.3 指標計算

| 指標 | 計算公式 |
|------|---------|
| Total Task | `COUNT(*) WHERE task_status IN ('TODO', 'DOING', 'DONE') AND is_excluded = 0` |
| Todo | `COUNT(*) WHERE task_status = 'TODO' AND is_excluded = 0` |
| Doing | `COUNT(*) WHERE task_status = 'DOING' AND is_excluded = 0` |
| Done | `COUNT(*) WHERE task_status = 'DONE' AND is_excluded = 0` |
| Todo % | `Todo / Total Task * 100` |
| Doing % | `Doing / Total Task * 100` |
| Done % | `Done / Total Task * 100` |

### 6.3 執行順序

```
1. Bronze 同步
   python sync/sync_incremental.py all
   
2. Silver 轉換
   python scripts/transform_silver_generic_metrics.py
   
3. Gold 快照
   python scripts/create_gold_generic_metrics_snapshot.py --date 2026-01-16
```

### 6.4 相關檔案

| 檔案 | 用途 |
|------|------|
| `sql/08_create_silver_generic_metrics.sql` | Silver 層 DDL |
| `sql/09_create_gold_generic_metrics.sql` | Gold 層 DDL |
| `scripts/transform_silver_generic_metrics.py` | Silver 層轉換腳本 |
| `scripts/create_gold_generic_metrics_snapshot.py` | Gold 層快照腳本 |
| `docs/metric_definitions.md` | L5 業務定義文件 |
