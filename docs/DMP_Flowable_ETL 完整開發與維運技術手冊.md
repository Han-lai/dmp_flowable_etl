# DMP Flowable - ETL 完整開發與維運技術手冊

這份文件整合了本系統從基礎架構、開發環境、目錄結構、核心程式碼、維運稽核、到開發擴充 SOP 的所有細節。旨在讓任何層級的開發者（甚至是對 ClickHouse 不熟悉的新手）都能快速上手並進行維護。

本手冊只有兩個使用時機，請先確認你的情境：

| 你的情況 | 跳到哪裡 |
|---|---|
| **第一次在這台機器跑**（或資料全部清掉要重建） | → [Part 1：初次建置](#part-1初次建置) |
| **每天例行更新資料** | → [Part 2：日常維運](#part-2日常維運) |

---

## 🎓 教學課程：五個核心步驟

> 教學時學員只需要按順序執行以下五條指令，完成後即可在 ClickHouse 看到完整的 KPI 資料。

| # | 目的 | 指令 |
|---|---|---|
| 1 | 建立資料庫結構 | `python scripts/etl/setup_schema.py` |
| 2 | 從 MSSQL 拉取原始資料 | `python scripts/etl/sync_unified_odbc.py --table all` |
| 3 | Bronze → Silver → Gold 計算 | `python scripts/etl/execute_etl.py --backfill --low-ram` |
| 4 | 確認各層資料量 | `python scripts/etl/execute_etl.py --status` |
| 5 | 業務數字稽核驗證 | `python scripts/etl/audit_done_details.py --date 2025-12-31 --status done` |

每一步的詳細說明與預期輸出請見 [Part 1：初次建置](#part-1初次建置)。

---

## 系統概覽

### 資料流向圖

```
  ┌──────────────────────────────────────┐
  │           MSSQL（來源系統）           │
  │  APP_SRV_BPM      APP_SRV_COMMON     │
  │  ├─ 任務執行紀錄   ├─ 人員主檔        │
  │  ├─ 業務變數       ├─ 組織主檔        │
  │  └─ 流程實例       └─ MDM 主檔        │
  └─────────────────┬────────────────────┘
                    │
                    │  Step 2
                    │  sync_unified_odbc.py
                    │  設定：config/sync_tables.yaml
                    │  主檔 → 全量覆蓋
                    │  流水帳 → 增量追加（Watermark）
                    ▼
  ┌──────────────────────────────────────┐
  │         Bronze 層（ClickHouse）       │
  │  bpm_act_hi_taskinst  任務執行紀錄   │
  │  bpm_act_hi_varinst   業務變數       │  ← 原始資料 1:1 複製
  │  bpm_act_hi_procinst  流程實例       │    不做任何加工
  │  common_hr_employee   人員主檔       │
  │  common_mdm_*         MDM 組織主檔   │
  └─────────────────┬────────────────────┘
                    │
                    │  Step 3
                    │  execute_etl.py --backfill
                    │  設定：config/pipeline_config.yaml
                    │
                    │  [A] backfill_pivot.sql
                    │      業務變數 Key-Value → 欄位寬表
                    ▼
  ┌──────────────────────────────────────┐
  │      silver.mv_varinst_pivoted       │
  │  每個流程 ID 一行，每個變數一欄       │
  └─────────────────┬────────────────────┘
                    │
                    │  [B] backfill_silver.sql（大 JOIN）
                    │      任務 + 流程 + 人員 + 變數 + MDM
                    │  [C] backfill_exclusion.sql
                    │      二次修正排除旗標
                    ▼
  ┌──────────────────────────────────────┐
  │        silver.mv_fact_task_vx        │
  │  ★ 核心事實表，所有 KPI 的唯一來源   │
  │  每筆 = 一個任務執行實例              │
  │  含：時間軸、結算狀態、五階維度、      │
  │      業務變數、排除旗標               │
  └─────────────────┬────────────────────┘
                    │
                    │  [D] backfill_gold_milestone.sql
                    │      Bitmap 壓縮聚合 TODO/DOING/DONE
                    │  [E] backfill_gold_acc.sql
                    │      7 天展開計算每日 WIP 負荷量
                    │  [F] backfill_gold.sql
                    │      Milestone + ACC 合併
                    ▼
  ┌──────────────────────────────────────┐
  │       Gold 層（Bitmap 中間表）         │
  │  rmv_l5_milestone_phys               │
  │      以開單日為單位的 Bitmap：         │
  │      todo/doing/done × 日/週/月       │
  │  rmv_l5_acc_phys                     │
  │      每日 WIP 負荷量 Bitmap           │
  │  rmv_l5_task_completion_phys         │
  │      Milestone + ACC 合併結果         │
  └─────────────────┬────────────────────┘
                    │
                    │  [G] backfill_gold_summary_historical.sql
                    │      （< 2026-04-01，歷史邏輯）
                    │  [H] backfill_gold_summary.sql
                    │      （>= 2026-04-01，現行邏輯）
                    │      Bitmap 聯集去重 → 預聚合成整數
                    ▼
  ┌──────────────────────────────────────┐
  │      Gold 層（對外表，純整數）          │
  │  rmv_l5_task_summary                 │
  │      period_type = Day / Week / Month │
  │      total/todo/doing/done/acc _qty   │
  │      ⚠ 查詢必須加 FINAL                │
  └─────────────────┬────────────────────┘
                    │
                    │  Cube.js 語意層
                    │  cube/model/cubes/cube_l5_task_periodic.js
                    │  對整數欄位做 SUM，查詢時不運算 Bitmap
                    ▼
  ┌──────────────────────────────────────┐
  │         Cube.js：L5TaskPeriodic      │
  │                                      │
  │  Day（最近 7 天）                     │
  │  └─ ACC Rate = acc ÷ acc_total_task  │
  │                                      │
  │  Week（當週 Wx、前一週 Wx-1、Wx-2）   │
  │  └─ ACC Rate = (todo+doing) ÷ total  │
  │                                      │
  │  Month（當月）                        │
  │  └─ ACC Rate = (todo+doing) ÷ total  │
  │                                      │
  │  費率一律 floor()，禁止 round()        │
  └─────────────────┬────────────────────┘
                    │
                    ▼
               前端儀表板
```

---

### 專案目錄結構

```
dmp_flowable/
│
├── scripts/etl/                      ← 📌 日常操作只需用這個資料夾
│   ├── setup_schema.py               Step 1：建立資料庫結構
│   ├── sync_unified_odbc.py          Step 2：MSSQL → Bronze 同步
│   ├── execute_etl.py                Step 3：Bronze → Silver → Gold 運算
│   ├── audit_done_details.py         Step 4：業務稽核驗證
│   ├── daily_etl_wrapper.sh          日常維運一鍵腳本（Step 2+3）
│   ├── init_pipeline.sh              初次建置一鍵腳本（Step 1+2+3）
│   ├── config/
│   │   ├── infra_config.yaml         setup_schema.py 讀取（建表清單與順序）
│   │   ├── pipeline_config.yaml      execute_etl.py 讀取（SQL 執行順序）
│   │   └── sync_tables.yaml          sync_unified_odbc.py 讀取（來源表設定）
│   └── tools/                        一次性工具，不在排程內
│       ├── export_l5_to_s3.sh        單月／單線體明細匯出至 S3
│       └── export_l5_all_months.sql  全月份明細匯出至 S3（UAT 對帳用）
│
├── sql/etl/
│   ├── schema/                       ← setup_schema.py 調度
│   │   │                               只定義欄位結構，不含業務邏輯
│   │   ├── 00_meta_checkpoint.sql    建立 ETL 執行進度紀錄表
│   │   ├── 01_bronze_flowable_core.sql  建立 Bronze 層 Flowable 核心表
│   │   ├── 02_bronze_common_dims.sql    建立 Bronze 層人員/MDM 主檔表
│   │   ├── 03_silver_pivot_and_hierarchy.sql  建立變數轉置暫存表
│   │   ├── 04_silver_fact_tasks.sql     建立核心事實寬表
│   │   ├── 06_gold_kpi_task_completion.sql   建立 Gold 層 Bitmap 中間表
│   │   └── 06b_gold_kpi_task_summary.sql     建立 Gold 層對外彙總表（整數）
│   │
│   └── dml/                          ← execute_etl.py 調度
│       │                               業務邏輯在這裡，維護時改這裡
│       ├── backfill_pivot.sql        [A] 變數 Key-Value 轉欄位
│       ├── backfill_silver.sql       [B] 核心事實寬表大 JOIN
│       ├── backfill_exclusion.sql    [C] 排除旗標二次修正
│       ├── backfill_gold_milestone.sql  [D] Bitmap KPI 聚合
│       ├── backfill_gold_acc.sql     [E] WIP 負荷量計算
│       ├── backfill_gold.sql         [F] 合併 milestone + acc
│       ├── backfill_gold_summary_historical.sql  [G] 對外彙總（< 2026-04-01）
│       ├── backfill_gold_summary.sql             [H] 對外彙總（>= 2026-04-01）
│       └── init_dim_mfg_five_level.sql           五階維度初始化（單次執行）
│
├── cube/model/                       ← Cube.js 語意層（獨立服務）
│   ├── cubes/
│   │   ├── cube_l5_task_periodic.js       週期感知 KPI 聚合（主力）
│   │   ├── cube_l5_task_periodic_pivot.js 週期 KPI 樞紐視圖
│   │   └── cube_l5_task_details.js        任務明細
│   └── views/
│       └── view_historical_trends.js      歷史趨勢視圖
│
├── api/                              FastAPI 服務（獨立部署，含 Dockerfile）
├── infra/                            docker-compose 與 .env（連線資訊，不進版控）
├── tests/                            單元測試（python -m pytest tests/ -v）
├── memory-bank/                      專案工作記憶
└── docs/                             文件（本檔案所在）
```

> 上表只列與 ETL 維運直接相關的檔案。`logs/`、`exports/`、`venv/`、`__pycache__/` 為執行產物或環境目錄，不需理會。

---

### Cube.js 的角色說明

Gold 層分成兩段：**中間表存 Bitmap**（用來去重），**對外表存預先算好的整數**。Cube.js 只讀對外表 `gold.rmv_l5_task_summary`，直接對整數欄位做 `SUM`，**不在查詢時運算 Bitmap**。

```
gold.rmv_l5_milestone_phys        ← Bitmap 中間表（todo/doing/done）
gold.rmv_l5_acc_phys              ← Bitmap 中間表（7 天滾動積壓）
        ↓ backfill_gold.sql（合併兩表）
gold.rmv_l5_task_completion_phys  ← Bitmap 中間表
        ↓ backfill_gold_summary*.sql（Bitmap 聯集 → 整數）
gold.rmv_l5_task_summary          ← 對外表，Cube.js 與所有報表的唯一入口
```

**查詢 `gold.rmv_l5_task_summary` 必須加 `FINAL`**（ReplacingMergeTree 特性，未加會讀到重複或舊版本列）。

#### 三種時間粒度

| 粒度 | 對應資料範圍 | 結算欄位 | ACC Rate 計算方式 |
|---|---|---|---|
| **Day** | 基準日往前 7 天，各自獨立 | `todo_daily` / `doing_daily` / `done_daily` | `acc ÷ acc_total_task`（7日滾動） |
| **Week** | 當週（Wx）、前一週（Wx-1）、前兩週（Wx-2） | `todo_weekly` / `doing_weekly` / `done_weekly` | `(todo + doing) ÷ total` |
| **Month** | 當月所有天 | `todo_monthly` / `doing_monthly` / `done_monthly` | `(todo + doing) ÷ total` |

#### 關鍵技術：Bitmap 跨日聯集（發生在 ETL 階段，不是查詢時）

milestone 中間表以**開單日**為單位，每一列存一張 Bitmap（內容是 task_id 的集合）。`backfill_gold_summary.sql` 把該週／該月範圍內所有列的 Bitmap 做聯集後算出去重數量，寫成整數存進 `rmv_l5_task_summary`：

```
週 todo = Bitmap(週一開單的 todo_weekly) ∪ ... ∪ Bitmap(週日開單的 todo_weekly)
```

**注意聯集的是 `todo_weekly` 欄位，不是 `todo_daily`**。`todo_weekly` 在寫入時已用「週日結算」的語意算好，聯集只是把整週各開單日的集合合併起來。

用 Bitmap 而非 `COUNT` 的原因：同一個 task_id 即使出現在多列，聯集後仍只算一次，**不會重複計數**。

> **💡 小技巧：如何在 ClickHouse 原生終端機查詢 Bitmap 欄位？**
> 
> 因為資料在 ClickHouse 底層是用 Bitmap 格式儲存，如果您直接用 `SELECT todo_daily FROM gold.rmv_l5_milestone_phys` 查詢，畫面會顯示為 `[ClickHouseRoaring64NavigableMap]` 這樣無法直接閱讀的結構。
> 為了能夠直觀地驗證資料，請搭配 ClickHouse 內建的 Bitmap 函數：
> - **若要看數量（有幾個任務）**：請搭配 `GROUP BY` 使用 `groupBitmapMerge(todo_daily)`，它會自動合併對應維度的 Bitmap 並回傳長度（任務數量整數）。
> - **若要看內容（具體包含哪些 Task ID）**：請搭配 `GROUP BY` 使用 `bitmapToArray(groupBitmapMergeState(todo_daily))`，它會將合併後的 Bitmap 展開為 Task ID 陣列。
> 
> **👇 實戰範例：查詢 CNE WJ2 NBU E5 在 2025-12-25 到 2025-12-31 的每日各狀態任務數**
> ```sql
> SELECT 
>     snapshot_date,
>     groupBitmapMerge(todo_daily) AS todo_count,
>     groupBitmapMerge(doing_daily) AS doing_count,
>     groupBitmapMerge(done_daily) AS done_count
> FROM gold.rmv_l5_milestone_phys
> WHERE region = 'CNE' 
>   AND plant = 'WJ2' 
>   AND factory = 'NBU' 
>   AND line = 'E5'
>   AND snapshot_date BETWEEN '2025-12-25' AND '2025-12-31'
> GROUP BY snapshot_date
> ORDER BY snapshot_date;
> ```

#### ACC Rate 的兩種算法

- **Day 粒度**：分母是 `acc_total_task`（7 天內開單任務總量，不含當天之後的新增），反映當下的積壓狀況
- **Week / Month 粒度**：分母改用 `total`（該週期內開單總量），反映整個週期的落後率

---

#### ACC（積壓率）的計算概念

**定義**：某一天，過去 7 天內開單、但截至當天仍**未完成**的任務數量，佔同窗口總開單數的比率。

```
ACC 分子 = 過去 7 天開單，且截至今天尚未完成（end_date 為空 或 end_date > 今天）
ACC 分母 = 過去 7 天的總開單數（acc_total_task）

ACC Rate = ACC 分子 ÷ ACC 分母
```

**為什麼要用 7 天滾動窗口？**  
若只看「今天開單、今天未完成」，數字會因為任務本來就需要多天作業而虛高。7 天窗口過濾掉了剛開單的正常進行中任務，**突顯真正在積壓的 WIP 量**。

**以 2025-12-25 為例**（CNE/WJ2/NBU/E5）：
- 12/19 ～ 12/25 這 7 天共開了 548 個任務（acc_total_task = 548）
- 其中有 40 個到 12/25 仍未完成（acc = 40）
- 積壓率 = 40 ÷ 548 ≈ **7.3%**

---

#### Weekly（週結算）的 Cohort 概念

**Cohort（梯次）定義**：同一個 ISO 週內開單的所有任務，屬於同一個週梯次，彼此互斥、不與其他週重疊。

```
週梯次狀態判定（一律以「該週週日」為結算點，不是查詢當天）：
  DONE  ← 本週開單，且完工日 ≤ 週日
  DOING ← 本週開單，認領日 ≤ 週日，且完工日為空或 > 週日
  TODO  ← 本週開單，至週日仍未被認領
```

> **⚠️ 結算點不是「查詢當天」**：一筆週一開單、週三被認領的任務，在週日結算時已是「已認領」，故整週歸入 DOING，**不會**因為它週一、週二曾是 TODO 就計入 TODO。`todo` 的語意是「**至週日仍未被認領**」，而非「本週曾出現未認領狀態」。

**為什麼 todo + doing + done = total 是固定的？**  
因為分母就是「本週開單總量」，三個狀態之和永遠等於總數，**沒有任何一筆任務被重複計算或遺漏**。

**Acc Rate（週落後率）**= `(todo + doing) ÷ total`，代表本週開單中，截至當下尚未完成的比率。

**以 W52（2025-12-22 ～ 12-28）為例**：
- 本週共開單 583 個（total = 583）
- 537 個在週內完成（done），29 個 TODO、17 個 DOING
- 落後率 = (29 + 17) ÷ 583 ≈ **7.9%**

**W49（12-01 ～ 12-06）落後率 = 0%** 的原因：查詢時間點（12/31）已超過 W49 結束，所有任務都已到達最終狀態，故 done = 298（等於 total），todo = doing = 0。

---

#### Monthly（月結算）的 Cohort 概念

邏輯與 Weekly 完全相同，只是梯次的邊界從「ISO 週」換成「自然月」：

```
月梯次狀態判定（一律以「該月最後一日」為結算點，不是查詢當天）：
  DONE  ← 本月開單，且完工日 ≤ 月底
  DOING ← 本月開單，認領日 ≤ 月底，且完工日為空或 > 月底
  TODO  ← 本月開單，至月底仍未被認領

月 Acc Rate = (todo + doing) ÷ total
```

**以 2025-12 為例**：
- 12 月共開單 2,294 個（total = 2,294）
- 2,189 個在月底前完成，剩餘 12 TODO + 93 DOING 尚未結清
- 月落後率 = (12 + 93) ÷ 2,294 ≈ **4.6%**

**Day / Weekly / Monthly 三者的差異總結**：

| 指標 | 分母 | 積壓定義 | 適合用來看 |
|---|---|---|---|
| **Daily ACC** | 過去 7 天開單總量 | 7 天內開單但當天仍未完成 | 即時 WIP 負荷壓力 |
| **Weekly Acc Rate** | 本週開單總量 | 本週開單但週末前未完成 | 週度計畫達成率 |
| **Monthly Acc Rate** | 本月開單總量 | 本月開單但月底前未完成 | 月度計畫達成率 |

---

## Part 1：初次建置

依序執行以下步驟。**每一步完成後，確認輸出正常再繼續下一步。**

---

### Step 1 — 建立資料庫結構

> **目的**：在 ClickHouse 裡建立 `bronze`、`silver`、`gold` 三層資料庫與所有空白的資料表。
> **執行時機**：只有在「第一次建置」或「schema 有更新」時才需要執行。

```bash
python scripts/etl/setup_schema.py
```

**✅ 成功的樣子**：終端機逐行印出「CREATE TABLE IF NOT EXISTS ... OK」之類的建表日誌，最後沒有 Error。

---

### Step 2 — 從 MSSQL 拉取資料到 Bronze 層

> **目的**：透過 ODBC 連線，把 MSSQL 的原始資料完整複製一份到 ClickHouse 的 `bronze` 資料庫。這一步純粹是「搬資料」，完全不做任何運算或轉換。
> **執行時機**：初次建置，以及每次需要更新原始資料時。

```bash
python scripts/etl/sync_unified_odbc.py --table all
```

**✅ 成功的樣子**：每張表都印出「Synced X rows → bronze.xxx」，最後沒有 Error。

**⚠️ 如果只想先測試某一張表是否能連線：**
```bash
python scripts/etl/sync_unified_odbc.py --table hr_employee
```

可同步的表名稱定義在 `scripts/etl/config/sync_tables.yaml`。**`--table` 要帶的是 YAML 的區塊名稱，不是 ClickHouse 的目標表名**：
- `hr_employee`、`emp_node_role`、`emp_org_info`、`mdm_*` 等 — 人員／MDM 主檔（`strategy: full`，全量覆蓋）
- `taskinst`、`varinst`、`procinst`、`identitylink` — Flowable 任務流水帳（`strategy: batch`，依時間窗增量）

例如目標表 `bronze.bpm_act_hi_taskinst` 的區塊名稱是 `taskinst`，指令要寫 `--table taskinst`。

---

### Step 3 — 計算轉換（Bronze → Silver → Gold）

> **目的**：對 Bronze 層的原始資料進行清洗、JOIN、KPI 計算，產出最終可查詢的 Gold 層指標表。
> **執行時機**：初次建置做完 Step 2 之後。這裡的 SQL 邏輯已經寫好，你只需要執行指令即可。

```bash
python scripts/etl/execute_etl.py --backfill --low-ram
```

**✅ 成功的樣子**：逐段印出「Processing silver_varinst_pivoted: 2025-01-01 ~ 2025-01-10 ... [Success] 12.3s」，最後印出「All calculation phases completed successfully!」

計算分兩個階段，程式會自動依序執行：
1. **Pivot（變數轉置）** → 寫入 `silver.mv_varinst_pivoted`
2. **Fact + Gold KPI** → 寫入 `silver.mv_fact_task_vx` 與 `gold.*`

**⚠️ 如果只需要計算特定時間段（例如補算某段缺失資料）：**
```bash
python scripts/etl/execute_etl.py --backfill --start 2025-06-01 --end 2025-12-31 --low-ram
```

**📌 三種執行模式的差異：**

| 參數 | 適用時機 | 處理的時間範圍 |
|---|---|---|
| `--backfill` | 初次建置、全量重算 | 所有歷史資料（從最早到今天） |
| `--daily` | 每日例行更新 | 最近幾天（增量，速度快） |
| `--start` / `--end` | 補算特定缺失區間 | 指定的起迄日期範圍 |

---

### Step 4 — 確認資料是否正確落地

執行完 Step 3 後，用以下指令快速核對各層資料量：

```bash
python scripts/etl/execute_etl.py --status
```

**✅ 成功的樣子**：顯示各層資料表的列數 (Rows) 與磁碟大小，`silver` 和 `gold` 的數字應該都大於 0。

若需要進一步核對業務數字（例如：比對 KPI 是否跟舊系統一致）：
```bash
python scripts/etl/audit_done_details.py --date 2026-05-12 --status done
```

---

## Part 2：日常維運

> 只有在第一次建置完成之後，日常才切換到這個模式。每天只需執行一條指令，它會自動：
> 1. 從 MSSQL 增量拉取有更新的資料（不會重複搬已有的資料）
> 2. 重新計算增量範圍內的 Silver / Gold 指標

**增量範圍怎麼決定**：`--daily` 不是固定回算 N 天，而是取
`起點 = min(上次成功的 checkpoint, Bronze 資料水位線) − 1 天`、`終點 = Bronze 同步水位線`。
實際範圍會隨 checkpoint 與 Bronze 水位線變動，可用 `--status` 或查 `ops_metrics.etl_checkpoint` 確認。

> **⚠️ 開單日過久的任務不會被重算**：`backfill_gold_milestone.sql` 是以 `task_start_date` 篩選要重算哪些任務。開單日一旦落到增量範圍之外，該批任務就不再更新——之後才發生的認領／完工雖會寫進 Silver，Gold 的 Week／Month 狀態卻會停在舊值。需要修正時，對該開單日執行 `--backfill`（先刪除既有列，見「遇到問題時」章節）。

```bash
bash scripts/etl/daily_etl_wrapper.sh
```

---

## 遇到問題時

### 記憶體不足（Memory Limit Exceeded / Code: 241）
加上 `--low-ram`。如果已經有這個參數還是 OOM，系統會自動把時間窗口切半重試，通常等待即可。

### 資料沒更新，但程式說「跳過，已完成」
計算進度記錄在 `ops_metrics.etl_checkpoint`。該時段狀態已是 `SUCCESS` 所以被跳過。
強制從頭重算：
```bash
python scripts/etl/execute_etl.py --reset --backfill --low-ram
```
> ⚠️ `--reset` 只清 Silver / Gold，Bronze 原始資料不受影響。

### ODBC 連線失敗
確認能連上 MSSQL 伺服器，並檢查環境變數是否已載入。**實際值一律放在 `infra/.env`（不進版控），不要寫死在文件或程式碼裡**：

```bash
set -a && . infra/.env && set +a    # 載入
env | grep -E 'CLICKHOUSE_HOST|MSSQL_USER|ODBC_DSN'   # 確認已載入（不印密碼）
```

| 變數 | 說明 |
|---|---|
| `MSSQL_USER` | MSSQL 連線帳號 |
| `MSSQL_PASSWORD` | MSSQL 密碼。**留空會導致同步失敗**（fail-loud，不會清空資料） |
| `ODBC_DSN` | ODBC DSN 名稱，預設 `MSSQL_DSN`，通常無需覆寫 |
| `CLICKHOUSE_HOST` | ClickHouse 主機位址 |
| `CLICKHOUSE_PASSWORD` | ClickHouse 密碼 |

### ClickHouse 連線不通（Connection refused / Timeout）
先用 curl 確認服務是否正常（先載入 `infra/.env`）：
```bash
curl "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT:-8123}/ping"
# 成功會回傳 Ok.
```
如果 ping 失敗，代表 ClickHouse 服務本身有問題，需通知 DBA 或確認 VPN 連線狀態，無法靠重跑腳本解決。

### Step 3 跑完，但 Silver / Gold 資料量是 0
Step 2（Bronze 同步）可能沒有成功執行完整。Silver 是基於 Bronze 計算，Bronze 沒有資料自然會全空，且程式不會報錯。

先確認 Bronze 是否有資料：
```sql
-- 在 DBeaver 或 ClickHouse 終端執行
SELECT count(*) FROM bronze.bpm_act_hi_taskinst;
-- 結果應該 > 0，如果是 0 請先重新執行 Step 2
```
確認 Bronze 有資料後，再搭配 `--reset` 重跑 Step 3：
```bash
python scripts/etl/execute_etl.py --reset --backfill --low-ram
```

### 執行 `--reset` 後，Gold 表的資料不見了
這是**正常行為**，不是 Bug。`--reset` 會清空 Silver / Gold 的計算結果，再從 Bronze 重新計算。  
等 `execute_etl.py` 跑完後，資料就會重新出現。如果跑完還是沒有，請參考上方「Silver / Gold 資料量是 0」的排查步驟。

### 某個任務明明已完工，Week / Month 卻還顯示 TODO

**成因**：`backfill_gold_milestone.sql` 以 `task_start_date` 決定要重算哪些任務。開單日一旦落到 `--daily` 的增量範圍之外，該批任務就不再更新；之後才發生的認領／完工會寫進 Silver，但 Gold 讀不到。Day 粒度不受影響（它只需開單當天的事件）。

**修正方式**：對該開單日重跑 backfill。因為 `rmv_l5_milestone_phys` 是 `AggregatingMergeTree`（Bitmap 用 OR 合併，**不是覆寫**），直接重跑會讓同一個任務同時殘留在新舊兩個狀態的 Bitmap 裡，**必須先刪除既有列**：

```bash
# 1. 先刪除該開單日的既有 Bitmap 列（破壞性操作，執行前確認日期正確）
docker exec -it clickhouse-server-odbc clickhouse-client --query \
  "ALTER TABLE gold.rmv_l5_milestone_phys DELETE WHERE snapshot_date = '2026-04-15'"

# 2. 再重跑該日期
python scripts/etl/execute_etl.py --backfill --start 2026-04-15 --end 2026-04-15 --low-ram
```

---

## 附錄：SQL 檔案總覽與維護指南

**平常執行不需要碰 SQL。** 只有在「業務邏輯要修改」時（例如新增排除規則、修改 KPI 公式）才需要編輯 SQL，改完後執行 `execute_etl.py --daily` 讓新邏輯生效。

SQL 分兩個資料夾，職責完全不同：

```
sql/etl/
├── schema/   ← 定義「表的欄位結構」，只有 setup_schema.py 會讀它
└── dml/      ← 定義「業務邏輯與計算」，只有 execute_etl.py 會讀它
```

---

### Schema 資料夾（`sql/etl/schema/`）

> **由 `setup_schema.py` 呼叫，按編號順序執行一次。**  
> 這裡只定義「表有哪些欄位」，不含任何業務計算。結構有變動才需要修改這裡。

| 檔案 | 建立的資料表 | 說明 |
|---|---|---|
| `00_meta_checkpoint.sql` | `ops_metrics.etl_checkpoint` | ETL 執行進度紀錄表，記錄每個時間窗口的執行狀態 |
| `01_bronze_flowable_core.sql` | `bronze.bpm_act_hi_taskinst` 等 | Flowable 核心流程表（任務、流程實例、流程定義、變數） |
| `02_bronze_common_dims.sql` | `bronze.common_hr_employee` 等 | 人員、組織、MDM 主檔的 Bronze 層表 |
| `03_silver_pivot_and_hierarchy.sql` | `silver.mv_varinst_pivoted` | 業務變數轉置結果暫存表 |
| `04_silver_fact_tasks.sql` | `silver.mv_fact_task_vx` | **核心事實寬表**，所有 KPI 的資料來源 |
| `06_gold_kpi_task_completion.sql` | `gold.rmv_l5_milestone_phys` 等 | Gold 層三張 Bitmap 中間表（milestone／acc／completion） |
| `06b_gold_kpi_task_summary.sql` | `gold.rmv_l5_task_summary` | **Gold 層對外表**（純整數，Cube.js 與報表的唯一入口） |

---

### DML 資料夾（`sql/etl/dml/`）

> **由 `execute_etl.py` 依照 `pipeline_config.yaml` 的順序呼叫。**  
> Python 會把 `{start_ts}` / `{end_ts}` 等時間佔位符替換為實際日期後再執行。  
> **這裡才是業務邏輯所在地，維護時主要改這裡。**

#### 執行順序與各檔案職責

```
Step A  backfill_pivot.sql                    → silver.mv_varinst_pivoted
Step B  backfill_silver.sql                   → silver.mv_fact_task_vx  (大 JOIN)
Step C  backfill_exclusion.sql                → 更新 silver.mv_fact_task_vx 的排除旗標
Step D  backfill_gold_milestone.sql           → gold.rmv_l5_milestone_phys       (Bitmap)
Step E  backfill_gold_acc.sql                 → gold.rmv_l5_acc_phys             (Bitmap)
Step F  backfill_gold.sql                     → gold.rmv_l5_task_completion_phys (Bitmap，合併 D+E)
Step G  backfill_gold_summary_historical.sql  → gold.rmv_l5_task_summary  (整數，< 2026-04-01)
Step H  backfill_gold_summary.sql             → gold.rmv_l5_task_summary  (整數，>= 2026-04-01)
```

**Step G / H 是雙管線**：同一張對外表 `gold.rmv_l5_task_summary` 由兩支 SQL 依時間邊界分別寫入，互不重疊。

| 粒度 | 邊界 | `< 邊界`（Step G 歷史邏輯） | `>= 邊界`（Step H 現行邏輯） |
|---|---|---|---|
| Day | `2026-04-01` | 事件日：開單／認領／完工任一發生即計入，同任務可能多天重複計入 | 開單日 cohort：僅計入開單當天 |
| Week | `2026-03-30` | Cohort，狀態於週日評估 | 同左，公式一致 |
| Month | `2026-04-01` | Cohort，狀態於月底評估 | 同左，公式一致 |

**Day 粒度不可跨邊界比較**（兩側語意不同）；歷史邏輯下同一任務會重複計入多天，故「逐日 total 加總」不等於「該月 Month total」，此為設計行為。

---

#### `backfill_pivot.sql` — 業務變數轉置

**輸入**：`bronze.bpm_act_hi_varinst`（Key-Value 格式，每個變數一行）  
**輸出**：`silver.mv_varinst_pivoted`（每個流程 ID 一行，每個變數一欄）

Flowable 流程的業務資料以 Key-Value 存儲，例如同一個流程會有：

```
NAME_='plant',    TEXT_='WJ2'
NAME_='lineName', TEXT_='NBU-L01'
NAME_='moNumber', TEXT_='MO-20250512'
```

這個 SQL 把它們「攤平」成一行，方便後續 JOIN：

```sql
argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'plant')    AS varinst_plant
argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'lineName') AS varinst_lineName
argMaxIf(v.TEXT_, v.REV_, v.NAME_ = 'moNumber') AS varinst_moNumber
-- ... 共 15 個業務變數
```

`argMaxIf` 的意思是：同一個流程 ID 可能有多筆（人員修正過），取版本號 `REV_` 最大的那筆（最新值）。

**⚙️ 維護時機**：當 Flowable 流程新增了新的業務變數，需要在這裡加一行 `argMaxIf(...)` 並同步在 `schema/03_silver_pivot_and_hierarchy.sql` 新增對應欄位。

---

#### `backfill_silver.sql` — 核心事實寬表

**輸入**：`bronze.bpm_act_hi_taskinst` + `silver.mv_varinst_pivoted` + HR/MDM 主檔  
**輸出**：`silver.mv_fact_task_vx`（所有 KPI 的唯一資料來源）

這是系統最核心的 SQL，將多張表 JOIN 後產出一張「任務事實寬表」，包含：

**[A] 識別資訊**
- `task_id`、`proc_inst_id` — 任務與流程的唯一 ID
- `l4_process_id`、`l4_process_name` — L4 流程編號與名稱（從 `BUSINESS_STATUS_` 欄位取得）

**[B] 時間軸**
- `task_start_time`、`task_claim_time`、`task_end_time` — 任務的三個關鍵時間點
- `duration_min`、`processing_time_min` — 總時長與實際作業時長（分鐘）

**[C] 結算狀態（Cohort 邏輯）**

這是報表正確性的關鍵。同一個任務在不同週期粒度下，結算狀態可能不同：

```sql
-- 日結算：今天開的單，今天結束才算 DONE
status_daily  = CASE WHEN end_date = start_date THEN 'DONE' ... END

-- 週結算：本週開的單，本週結束前算 DONE（不管哪天）
status_weekly = CASE WHEN end_date <= (週起始 + 6天) THEN 'DONE' ... END

-- 月結算：本月開的單，本月底前算 DONE
status_monthly = CASE WHEN end_date <= 月底 THEN 'DONE' ... END
```

**[D] 五階維度**
- `vx_type` — 作業類型（V1/V2/V3），由 `TASK_DEF_KEY_` 前綴判定
- `region`、`plant`、`factory`、`line` — 從業務變數取值，若無則從 MDM 主檔推導

**[E] 排除旗標（`is_excluded`）**

KPI 只統計有商業意義的生產任務，以下幾種情況會被排除：

| 排除原因 | 判定條件 | `exclude_reason` |
|---|---|---|
| 自動完成節點 | `LONG_ = 1` | `bypass` |
| 系統帳號操作 | `EmpName = 'SYSTEM'` | `system_bypass` |
| 系統節點（E/C 開頭） | `TASK_DEF_KEY_ LIKE 'E%'` | `system_node` |
| 測試工單 | `moNumber LIKE 'Q%'` 或 `'R%'` | `Q_order` / `R_order` |
| 通知/虛擬任務 | `NAME_ LIKE '%Notify%'` | `notify_task` |

**⚙️ 新增排除規則的方法**：找到 `multiIf(...)` 段落，在最後一個 `0)` 之前插入新條件：
```sql
multiIf(
    tb.LONG_ = 1, 1,
    ...
    (t.NAME_ LIKE '%NewRule%'), 1,   ← 新增這行
    0) AS is_excluded
```
同步在 `exclude_reason` 的 `multiIf` 加上對應的描述字串。

---

#### `backfill_exclusion.sql` — 補充排除旗標修正

**時機**：在 `backfill_silver.sql` 之後執行，用 `ALTER TABLE ... UPDATE` 修正特定的排除旗標。  
目前負責修正 `autoComplete` 變數的邏輯（因 Flowable 的 LONG_ 欄位有時未正確寫入，需從變數表二次確認）。

---

#### `backfill_gold_milestone.sql` — KPI 任務完成指標（Bitmap 聚合）

**輸入**：`silver.mv_fact_task_vx`  
**輸出**：`gold.rmv_l5_milestone_phys`（按日期 × 五階維度預聚合）

使用 `groupBitmapStateIf` 把每個維度組合下的 Task ID 壓縮成 Bitmap 存儲，同時計算 TODO / DOING / DONE 三種狀態在日/週/月三個粒度下的數量。Bitmap 的好處是查詢時的去重計數速度極快，且支持跨時段的集合運算。

---

#### `backfill_gold_acc.sql` — 負荷量（ACC）指標

**輸入**：`silver.mv_fact_task_vx`  
**輸出**：`gold.rmv_l5_acc_phys`

使用 `ARRAY JOIN` 把任務在開單日起 7 天內每天都展開一筆，計算每天「進行中的 WIP 任務數」，用於衡量系統的實時負荷壓力。

---

#### `backfill_gold.sql` — 合併 Milestone 與 ACC

**輸入**：`gold.rmv_l5_milestone_phys` + `gold.rmv_l5_acc_phys`  
**輸出**：`gold.rmv_l5_task_completion_phys`（**Bitmap 中間表，非對外查詢用**）

把 Milestone 與 ACC 兩張表用 LEFT JOIN 合併成一張，並以 `bitmapOr(todo, doing, done)` 算出 `total_task`。輸出仍是 Bitmap 格式，供下一步 Step G／H 彙總。

---

#### `backfill_gold_summary_historical.sql` / `backfill_gold_summary.sql` — 對外彙總

**輸入**：`gold.rmv_l5_task_completion_phys`（現行邏輯）或 `silver.mv_fact_task_vx`（歷史邏輯）  
**輸出**：`gold.rmv_l5_task_summary`（**Cube.js 與所有報表的唯一入口**）

把 Bitmap 聯集去重後算成整數，依 `period_type`（Day／Week／Month）分別寫入。兩支 SQL 以 2026-04-01 為界分工，互不重疊：

- `backfill_gold_summary_historical.sql` 處理 `< 2026-04-01`，Day 採事件日語意，直接讀 Silver 計算。
- `backfill_gold_summary.sql` 處理 `>= 2026-04-01`，Day 採開單日 cohort，讀 `task_completion_phys` 的 Bitmap。

**⚙️ 維護時機**：修改 KPI 公式或費率算法時改這裡。費率一律用 `floor()`，**禁止 `round()`**——兩者在邊界值會產生不同百分比，與既有報表對不上。

---

### 新增業務邏輯的標準流程

#### 情境 A：新增一個業務變數（MSSQL 流程有新欄位要帶進來）

1. `sql/etl/schema/03_silver_pivot_and_hierarchy.sql`：在建表 DDL 新增欄位定義
2. `sql/etl/dml/backfill_pivot.sql`：新增一行 `argMaxIf(...)` 轉置邏輯
3. `sql/etl/schema/04_silver_fact_tasks.sql`：在建表 DDL 新增欄位定義
4. `sql/etl/dml/backfill_silver.sql`：在 SELECT 中加入對應的欄位
5. 執行：`python scripts/etl/setup_schema.py`（更新表結構）
6. 執行：`python scripts/etl/execute_etl.py --reset --backfill --low-ram`（重算）

#### 情境 B：新增排除規則

只需修改 `sql/etl/dml/backfill_silver.sql` 的 `multiIf` 段落，不需動 Schema。  
修改後：`python scripts/etl/execute_etl.py --reset --backfill --low-ram`

#### 情境 C：新增全新 KPI 指標

1. `sql/etl/schema/` 建立新的 Gold 表 DDL → 在 `infra_config.yaml` 註冊 → 執行 `setup_schema.py`
2. `sql/etl/dml/` 建立計算 SQL
3. `scripts/etl/config/pipeline_config.yaml` 新增 `steps` 項目（注意順序：中間表要排在 summary 之前）
4. **若新指標要讓前端看到**，還須在 `backfill_gold_summary.sql`／`backfill_gold_summary_historical.sql` 補上對應欄位，並在 `06b_gold_kpi_task_summary.sql` 加欄位——只寫進中間表，Cube.js 是讀不到的
5. `cube/model/cubes/cube_l5_task_periodic.js` 新增 measure
6. 執行：`python scripts/etl/execute_etl.py --daily`

---

## 附錄：Gold 層數據驗證基準

> 驗證環境：ClickHouse（連線資訊見 `infra/.env`）  
> 維度篩選：`region='CNE'`、`plant='WJ2'`、`factory='NBU'`、`line='E5'`  
> 時間區間：2025-12-25 ～ 2025-12-31

修改管線後，用下列查詢比對基準數字確認結果一致（本節數字已於 2026-08-06 實測，與下表相符）：

```sql
SELECT
    snapshot_date,
    groupBitmapMerge(todo_daily)  AS todo,
    groupBitmapMerge(doing_daily) AS doing,
    groupBitmapMerge(done_daily)  AS done
FROM gold.rmv_l5_milestone_phys
WHERE region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5'
  AND snapshot_date BETWEEN '2025-12-25' AND '2025-12-31'
GROUP BY snapshot_date
ORDER BY snapshot_date;
```

把 `todo_daily` 換成 `todo_weekly` / `todo_monthly` 並改用對應的時間篩選，即可驗證週／月結算數字。

---

### Daily — 日結算 Milestone（`gold.rmv_l5_milestone_phys`）

| Date | Todo | Doing | Done | Total |
|---|---|---|---|---|
| 2025-12-25 | 26 | 0 | 154 | **180** |
| 2025-12-26 | 56 | 7 | 53 | **116** |
| 2025-12-27 | 14 | 3 | 44 | **61** |
| 2025-12-28 | 3 | 0 | 7 | **10** |
| 2025-12-29 | 3 | 9 | 48 | **60** |
| 2025-12-30 | 8 | 59 | 184 | **251** |
| 2025-12-31 | 9 | 5 | 186 | **200** |

---

### Daily ACC — 每日 WIP 負荷量（`gold.rmv_l5_acc_phys`）

ACC = 當天仍在進行中（7 天滾動視窗內尚未完成）的任務數；ACC Rate = `acc ÷ acc_total_task`。

| Date | Acc | Acc Total（7日窗口）| Acc Rate |
|---|---|---|---|
| 2025-12-25 | 40 | 548 | 7.3% |
| 2025-12-26 | 76 | 620 | 12.3% |
| 2025-12-27 | 44 | 578 | 7.6% |
| 2025-12-28 | 46 | 583 | 7.9% |
| 2025-12-29 | 40 | 599 | 6.7% |
| 2025-12-30 | 95 | 799 | 11.9% |
| 2025-12-31 | 97 | 878 | 11.0% |

---

### Weekly — 週結算（`gold.rmv_l5_milestone_phys`，12 月各 ISO 週）

Acc Rate = `(todo + doing) ÷ total`。W49 全部 Done 表示該週的開單任務在月底前已全部結清。

| ISO Week | 週起日 | 週末日 | Total | Todo | Doing | Done | Acc Rate |
|---|---|---|---|---|---|---|---|
| W49 | 2025-12-01 | 2025-12-06 | **298** | 0 | 0 | 298 | 0.0% |
| W50 | 2025-12-09 | 2025-12-14 | **400** | 15 | 38 | 347 | 13.2% |
| W51 | 2025-12-15 | 2025-12-21 | **502** | 19 | 12 | 471 | 6.2% |
| W52 | 2025-12-22 | 2025-12-28 | **583** | 29 | 17 | 537 | 7.9% |
| W1  | 2025-12-29 | 2025-12-31 | **511** | 7 | 71 | 433 | 15.3% |

---

### Monthly — 月結算（`gold.rmv_l5_milestone_phys`，2025-12）

| Year | Month | Total | Todo | Doing | Done | Acc Rate |
|---|---|---|---|---|---|---|
| 2025 | M12 | **2,294** | 12 | 93 | 2,189 | 4.6% |

整個 12 月共有 2,294 個任務；月底尚有 12 + 93 = 105 筆未結清（Acc Rate = 4.6%）。

---

## 附錄：Silver 明細表查詢實戰範例

當您需要進入「明細層」查詢具體的任務流水帳、機種、工單，甚至追蹤單一任務的生命週期時，核心事實寬表 `silver.mv_fact_task_vx` 就是唯一的真相來源（SSOT）。

以下提供四個最常用的明細查詢 SQL 範例：

### 1. 查詢特定日期與維度下「已完成 (DONE)」的任務明細
即當天開單且當天結案的任務明細：
```sql
SELECT 
    task_id, 
    proc_inst_id, 
    task_name, 
    assignee_name, 
    task_start_time, 
    task_end_time,
    model_name,        -- 機種名稱
    mo_number          -- 工單號碼
FROM silver.mv_fact_task_vx FINAL
WHERE region = 'CNE' 
  AND plant = 'WJ2' 
  AND factory = 'NBU' 
  AND line = 'E5'
  AND task_start_date = '2025-12-31'
  AND task_end_date = '2025-12-31'
  AND is_excluded = 0
ORDER BY task_end_time DESC;
```

### 2. 查詢特定日期下「待辦 (TODO)」或「進行中 (DOING)」的任務明細
- **待辦 (TODO)**：當天已開單，但未簽收（Claim）且未完成：
```sql
SELECT task_id, task_name, assignee_name, task_start_time, model_name
FROM silver.mv_fact_task_vx FINAL
WHERE region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
  AND task_start_date = '2025-12-31'
  AND COALESCE(task_claim_date, toDate('1900-01-01')) != '2025-12-31'
  AND (task_end_date IS NULL OR task_end_date != '2025-12-31')
  AND is_excluded = 0;
```

- **進行中 (DOING)**：當天已簽收（Claim）但未完成：
```sql
SELECT task_id, task_name, assignee_name, task_start_time, task_claim_time, model_name
FROM silver.mv_fact_task_vx FINAL
WHERE region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
  AND task_start_date = '2025-12-31'
  AND task_claim_date = '2025-12-31'
  AND (task_end_date IS NULL OR task_end_date != '2025-12-31')
  AND is_excluded = 0;
```

### 2.5 查詢特定日期下「持續累積（歷史積壓）」的待辦 (TODO) 或進行中 (DOING) 明細
*當您需要排查截至某個日期為止，歷史上所有「尚未解決」的真實產線 WIP 積壓時，請使用以下累積邏輯（不限於當天開單）：*

- **持續累積待辦 (TODO)**（在目標日期或之前開單，且截至該日結束時「未簽收」也「未完工」）：
```sql
SELECT task_id, task_name, assignee_name, task_start_date, model_name
FROM silver.mv_fact_task_vx FINAL
WHERE region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
  AND task_start_date <= '2025-12-31'
  AND (task_claim_date IS NULL OR task_claim_date > '2025-12-31')
  AND (task_end_date IS NULL OR task_end_date > '2025-12-31')
  AND is_excluded = 0
ORDER BY task_start_date ASC;  -- 最早開單優先（定位最久積壓）
```

- **持續累積進行中 (DOING)**（在目標日期或之前開單、且已簽收，但截至該日結束時「尚未完工」）：
```sql
SELECT task_id, task_name, assignee_name, task_start_date, task_claim_date, model_name
FROM silver.mv_fact_task_vx FINAL
WHERE region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
  AND task_start_date <= '2025-12-31'
  AND task_claim_date <= '2025-12-31'
  AND (task_end_date IS NULL OR task_end_date > '2025-12-31')
  AND is_excluded = 0
ORDER BY task_claim_date ASC; -- 最早簽收優先
```

### 3. 透過 Task ID 或流程實例 ID (Process ID) 追蹤單一任務
當您需要追溯某個異常任務的全部資訊（如歷時、是否被排除等）：
```sql
SELECT 
    task_id,
    proc_inst_id,
    task_name,
    task_status,
    assignee_name,
    duration_min,          -- 任務歷時 (分鐘)
    processing_time_min,   -- 簽收後處理時間 (分鐘)
    model_name,
    mo_number,
    exclude_reason,
    is_excluded
FROM silver.mv_fact_task_vx
WHERE task_id = '您的_TASK_ID' 
   OR proc_inst_id = '您的_PROCESS_INSTANCE_ID';
```

### 4. 查詢特定機種 (Model) 或工單 (MO) 的所有任務流轉軌跡
```sql
SELECT 
    task_primary_date,
    task_name,
    task_status,
    assignee_name,
    duration_min,
    line
FROM silver.mv_fact_task_vx
WHERE model_name = '您的_機種名稱' 
   OR mo_number = '您的_工單號碼'
ORDER BY task_start_time ASC;
```

