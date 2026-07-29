# DMP Flowable 系統參考文件

**版號**：v1.0（2026-07-29）

## 0. 文件說明

**系統**：MSSQL（Flowable BPM 生產庫）→ ODBC → ClickHouse 三層數倉（bronze/silver/gold）→ Cube.js，產出 L5 任務完成率等製造 KPI。生產運作中，每日排程自動增量。

**閱讀對象**：第一次接手此系統、不具備專案背景知識的工程師。讀完本文應能理解架構、看懂資料流向，並完成部署與日常維運。

**鐵律（適用全文）**：
- MSSQL 來源庫唯讀，嚴禁任何寫入/DDL。
- 連線資訊一律環境變數（`infra/.env`），程式碼不寫死 IP/密碼。
- `--reset`／`TRUNCATE`／`DROP` 類操作務必事先確認，本文件標註的破壞性指令皆已註明。

---

## 1. 架構設計

### 1.1 整體架構

```
┌─────────────────────┐
│  MSSQL (唯讀來源)      │
│  APP_SRV_BPM         │  Flowable 引擎事實表（任務/流程/變數）
│  APP_SRV_COMMON      │  HR / MDM 五階製造維度
└──────────┬───────────┘
           │ ODBC（Native C++ Bridge）
           ▼
┌─────────────────────────────────────────────┐
│  ClickHouse                                  │
│  ┌───────────┐   ┌───────────┐  ┌──────────┐│
│  │  bronze   │──▶│  silver   │─▶│   gold   ││
│  │ (原始鏡像) │   │ (清洗/攤平)│  │ (KPI彙總) ││
│  └───────────┘   └───────────┘  └──────────┘│
└───────────────────────┬───────────────────────┘
                         │
                         ▼
                 ┌───────────────┐
                 │   Cube.js      │
                 │  語義層/預聚合    │
                 └───────┬───────┘
                         ▼
                 前端 BI / Superset
```

各服務以 **split-stack** 方式獨立部署，各自有獨立的 `docker-compose.yml`，互不共用生命週期。

### 1.2 模組職責與相互關係

| 模組 | 職責 | 依賴 | 部署位置 |
|---|---|---|---|
| MSSQL `APP_SRV_BPM` | Flowable 引擎事實表：任務、流程實例、變數、身分關聯 | — | 既有生產環境，非本專案管理 |
| MSSQL `APP_SRV_COMMON` | HR 員工主檔、MDM 五階製造維度、權限對照 | — | 同上 |
| ETL 腳本群（`scripts/etl/`） | Bronze 同步、Silver/Gold 運算、排程入口 | ClickHouse、MSSQL | 主機本地執行（非容器化） |
| ClickHouse + ODBC bridge | 三層數倉主體，含 MSSQL 連線橋接 | MSSQL（ODBC） | `infra/clickhouse/odbc/` |
| Cube.js | 語義層，唯讀查詢 `gold.rmv_l5_task_summary` 做預聚合 | ClickHouse | `infra/cube/` |

**資料所有權**：ETL 腳本是資料流的唯一寫入端。Cube.js 對 ClickHouse 為唯讀。

### 1.3 Cube.js Model 結構

主力 KPI cube 為 `L5TaskPeriodic`（`cube/model/cubes/cube_l5_task_periodic.js`），資料來源為 `gold.rmv_l5_task_summary`，提供 Day/Week/Month 三種粒度的 total/todo/doing/done/acc 及費率 measures，供前端「7 天日趨勢 + 3 週對比 + 當月累計」視圖使用。所有 measures 直接對預聚合整數欄位做 `SUM`，不在查詢時即時運算 Bitmap；費率類 measures（`doneRate`/`doingRate`/`accRate` 等）皆採 `floor()`，與 2.6 節 Rule 2 一致。

### 1.4 技術棧與版本

| 項目 | 版本／規格 |
|---|---|
| ClickHouse | 25.8.18.1（客製 image，內建 Native ODBC，非官方原生映像） |
| ODBC 連線方式 | Native C++ ODBC Bridge（非 JDBC，非 Airbyte）——實測吞吐約 90,218 rows/s，為 JDBC 方案的 2.7 倍 |
| Python | 3.x，關鍵套件：`clickhouse-connect>=0.7.0`、`pyyaml>=6.0.0`、`pandas>=2.0.0` |
| Cube.js | 容器化部署 |


---

## 2. 業務邏輯

### 2.1 資料流總覽

**Bronze 層（19 張表）**：
- **15 張 full 策略**（維度表：HR、MDM 五階、權限對照等）：不吃時間窗，每次整批重抓。
  - 同步流程：建暫存表 → INSERT → 驗證列數 > 0 → 原子替換（RENAME 舊表 → RENAME 新表 → DROP 舊表）。
  - 此流程為**非破壞性**：密碼錯誤或連線失敗時原表不受影響，僅該次同步失敗。
- **4 張 batch 策略**（事實表：`taskinst`/`varinst`/`procinst`/`identitylink`）：依 `time_col` 切時間窗批次同步，透過 `_sync_watermark` 記錄進度以支援續跑。
- 所有事實表皆為 `ReplacingMergeTree`，`PARTITION BY toYYYYMM(時間欄)`，`TTL` 保留 **1 年**（超過一年自動過期刪除）。

**Silver/Gold 層（8 個計算階段，依序執行）**：

| 階段 | phase_id | 輸出表 | 職責 |
|---|---|---|---|
| 1 | `silver_varinst_pivoted` | `silver.mv_varinst_pivoted` | 將 EAV 格式的 `ACT_HI_VARINST` 攤平為寬表 |
| 2 | `silver_facts` | `silver.mv_fact_task_vx` | 核心任務事實表，含五階維度、vx_type、is_excluded 判定 |
| 3 | `silver_exclusion` | `silver.mv_fact_task_vx` | 更新自動完成任務的排除標記（UPDATE） |
| 4 | `gold_milestone` | `gold.rmv_l5_milestone_phys` | 里程碑指標 |
| 5 | `gold_acc` | `gold.rmv_l5_acc_phys` | 積壓（accumulate）指標，7 天滾動 Bitmap |
| 6 | `gold_unified` | `gold.rmv_l5_task_completion_phys` | 統一完成率明細 |
| 7 | `gold_summary_historical` | `gold.rmv_l5_task_summary` | **歷史邏輯管線**，處理 `< 2026-04-01` 的資料 |
| 8 | `gold_summary` | `gold.rmv_l5_task_summary` | **現行邏輯管線**，處理 `>= 2026-04-01` 的資料 |

`gold.rmv_l5_task_summary` 是 **Cube.js 與所有報表查詢的唯一入口**。查詢時必須加 `FINAL`（ReplacingMergeTree 特性，未加會讀到重複/舊版本列）。

### 2.2 新增或調整 MSSQL 同步表

Bronze 同步表清單集中定義於 `scripts/etl/config/sync_tables.yaml`，每張表一個區塊：

```yaml
<table_key>:
  source: "<MSSQL_DB>.dbo.<來源表名>"     # 例："APP_SRV_COMMON.dbo.HR_Employee_0503"
  target: "bronze.<目標表名>"             # 例："bronze.common_hr_employee"
  strategy: "full" | "batch"              # full=不吃時間窗、每次整批重抓；batch=依時間窗批次同步
  engine_ddl: "<明確欄位型別宣告>"          # 必填，ODBC 代理表用，見下方說明
  columns: "<SELECT 欄位清單>"             # 可用 "*" 或明確列出（可含轉換運算式）

  # 以下僅 strategy: batch 需要
  time_col: "<時間欄位>"                   # 用於切分時間窗的欄位，例如 START_TIME_
  step_days: 2                            # 每批次天數
  history_start: "2025-10-01"             # 無 watermark 時的起始回填日期
```

新增一張表需要**兩個步驟**，缺一不可：

**步驟 1：在 `sync_tables.yaml` 新增區塊**（格式如上）
- `engine_ddl` 必須明確宣告每個欄位的型別，不可省略或用 `SELECT *` 推斷型別取代。
- 目的：繞過 ODBC driver 對 LOB（`varchar(max)`/`xml`）欄位自動探測時的死鎖問題。

**步驟 2：在對應的 schema DDL 檔案新增 `CREATE TABLE IF NOT EXISTS bronze.<目標表名>`**
- Flowable 核心表加在 `sql/etl/schema/01_bronze_flowable_core.sql`；MSSQL COMMON 維度表加在 `sql/etl/schema/02_bronze_common_dims.sql`。
- 新增後執行 `init_pipeline.sh --phase 1` 部署。
- 目標表**必須先存在於 ClickHouse**，`sync_full()` 是以 `CREATE TABLE temp AS target` 複製既有目標表結構建暫存表，若目標表不存在會直接失敗——這就是步驟 2 不可省略的原因。

兩步驟皆完成後，`sync_unified_odbc.py --table all` 會自動掃描 `sync_tables.yaml` 的所有區塊逐一同步，不需要修改 Python 程式碼。若只是調整既有表的抓取欄位或時間窗策略，直接修改該表在 `sync_tables.yaml` 的對應欄位即可，同樣不需要改程式碼。

### 2.3 資料拉取的自適應切窗（MSSQL 減壓機制）

Bronze 同步（`sync_batch_adaptive()`）與 Silver/Gold 運算（`run_safe()`）皆內建自動切窗重試：遇到負載過高或 ClickHouse OOM（`Memory limit exceeded` / `Code: 241`）時，會將該時間區間對半切分後遞迴重試，藉此降低單次查詢對 MSSQL 與 ClickHouse 的瞬間負載。此機制自動觸發，無需人工設定。

### 2.4 Bronze 層：Watermark 與資料保留規則

`bronze._sync_watermark`（`ReplacingMergeTree`，每張表僅保留最新一列）記錄三個獨立欄位：

| 欄位 | 語意 | 誰在寫 |
|---|---|---|
| `sync_time` | 該次同步**實際執行**的時間（wall clock） | 每次同步皆寫入 `now()` |
| `last_sync_time` | 該次同步的**時間窗結尾**（batch 表）或執行時間（full 表） | 每個批次無條件寫入（含 0 筆批次） |
| `max_data_time` | 該表**實體資料**目前的最大時間，從物理表現查 | 僅在批次有寫入資料時才重查 |

**續跑點判斷**（`get_last_watermark()`）：
- 優先取 `max_data_time`：即使 `last_sync_time` 因手動指定過去的 `--end` 而被回撥，**不影響下次自動續跑的起點**。
- `--daily` 模式判斷增量結束點時改讀 `last_sync_time`：若被回撥且未先執行一次正常同步就直接跑 `--daily`，會導致計算不到最新資料。
- 正常排程流程（先 sync 後 daily）不會觸發上述問題，因為 sync 一定會先把 `last_sync_time` 寫回正確值。

**ReplacingMergeTree 去重語意**：
- `bpm_act_hi_varinst` 排序鍵為 `(PROC_INST_ID_, NAME_, CREATE_TIME_)`、`bpm_act_hi_identitylink` 為 `(TASK_ID_, USER_ID_, TYPE_)`，**皆非 MSSQL 主鍵**，同鍵多列會被去重合併為一列。
- 因此 bronze 筆數會低於 MSSQL 原始筆數，**屬正常行為**，非同步遺漏。
- `taskinst`/`procinst` 因排序鍵即為唯一鍵，兩端筆數會完全一致，可作為對帳基準。

**TTL 資料保留**：四張事實表 `TTL 時間欄 + INTERVAL 1 YEAR`，超過一年的資料會被 ClickHouse 自動清除，無法從 bronze 還原（需重新從 MSSQL 拉取，前提是來源仍保留）。

### 2.5 Silver 層：任務排除邏輯

**`is_excluded` 排除規則**（`silver.mv_fact_task_vx`）：任務符合以下任一條件即標記排除，不計入 KPI：

| 條件 | `exclude_reason` |
|---|---|
| 變數 `autoComplete=1` | `bypass` |
| 執行人為 `SYSTEM` 帳號 | `system_bypass` |
| `TASK_DEF_KEY_` 以 `E` 或 `C` 開頭（系統節點） | `system_node` |
| 工單號以 `Q` 或 `R` 開頭（測試單） | `Q_order` / `R_order` |
| 任務名稱含 `Notify` 或 `Dummy`（通知/虛擬任務） | — |

其中 `autoComplete_flag` 額外由獨立的 `backfill_exclusion.sql`（Phase 3）以 `ALTER TABLE ... UPDATE` 更新，涵蓋首次計算時 `ACT_HI_VARINST` 尚未寫入 `autoComplete` 變數的任務。

### 2.6 Gold 層：核心 KPI 定義

每個期別（Day/Week/Month）× 五階維度組合輸出以下欄位：

| 欄位 | 定義 |
|---|---|
| `total_qty` | 該期別任務總數 |
| `todo_qty` | 尚未開始 |
| `doing_qty` | 進行中（已認領未完成） |
| `done_qty` | 已完成 |
| `acc_qty` | 積壓（7 天滾動視窗），與 `total_qty` 無大小關係，不同口徑 |

**費率規則（Rule 2，全專案唯一標準）**：
```
rate = floor(qty * 100 / total)
```
一律無條件捨去（`floor`），**禁止使用 `round()`**——兩者在邊界值上會得到不同的百分比，與既有報表口徑不符會導致對帳失敗。

### 2.7 Gold 層：雙管線邊界與粒度語意

依業務需求，Day 粒度須支援兩種不同的統計口徑：歷史資料維持既有的「事件日」語意，現行資料改採「起始日 cohort」語意。因此同一張輸出表依時間邊界並存兩套計算邏輯：

| 粒度 | 邊界日期 | `< 邊界` 語意（歷史邏輯） | `>= 邊界` 語意（現行邏輯） |
|---|---|---|---|
| **Day** | `2026-04-01` | 事件日（開單/認領/完成任一發生即計入，同任務可能多天重複計入） | 起始日 cohort（僅計入開單當天，狀態於當下評估） |
| **Week** | `2026-03-30`（2026-W14 週一） | Cohort（`task_start_date` 為快照，狀態於週日評估） | 同左，公式一致 |
| **Month** | `2026-04-01` | Cohort（`task_start_date` 為快照，狀態於月底評估） | 同左，公式一致 |

**關鍵規則**：
- **Day 粒度不可跨邊界比較**：兩側語意不同，`2026-03-31` 與 `2026-04-01` 的 Day 數字口徑不一致。
- **Week/Month 上界一律對齊期末**：回填 SQL 的 `WHERE` 子句上界使用 `toStartOfWeek(...) + INTERVAL 6 DAY` / `toLastDayOfMonth(...)`，而非原始輸入的 `{end_ts}`。
  - 效果：不論 `--end` 落在期中何處，計算範圍都會自動延伸至該週/月結束，寫出的結果永遠是該期完整資料。
- **Day 粒度同一任務會重複計入多天**（歷史邏輯的事件日語意下），因此單月「逐日 total 加總」不等於「該月 Month total」，這是設計行為，非資料錯誤。

---

## 3. 部署與維運指令

部署順序：先啟動 ClickHouse，執行 `init_pipeline.sh` 將 MSSQL 資料拉取進 ClickHouse（Bronze）並運算出 Silver/Gold，確認資料到位後再啟動 Cube.js 對外提供查詢。以下指令皆可直接複製執行。所有連線資訊來自 `infra/.env`，執行前需先載入：

```bash
cd /path/to/dmp_flowable
set -a && . infra/.env && set +a
```

### 3.1 環境變數清單

`infra/.env`（版控外，需自行建立）：

```bash
VOLUMES_ROOT=/data/dmp_flowable          # docker volume 掛載根目錄
CLICKHOUSE_HOST=<ClickHouse 主機 IP>
CLICKHOUSE_PORT=8123
CLICKHOUSE_USERNAME=default
CLICKHOUSE_PASSWORD=<ClickHouse 密碼>
CUBEJS_API_SECRET=<Cube.js API 密鑰>
```

執行 Phase 2（MSSQL 同步）額外需要：

```bash
export MSSQL_USER=APP_SRV_BPM
export MSSQL_PASSWORD=<MSSQL 密碼>       # 留空會導致同步失敗（fail-loud，不會清空資料）
export ODBC_DSN=MSSQL_DSN                # 預設值，通常無需覆寫
```

### 3.2 服務啟動指令

```bash
# ClickHouse + ODBC bridge（資料倉儲主體）
docker-compose -f infra/clickhouse/odbc/docker-compose-odbc.yml up -d

# Cube.js（語義層，對外埠 4002/4003）
docker-compose -f infra/cube/docker-compose.yml up -d
```

### 3.3 初次建置——唯一入口 `init_pipeline.sh`

`init_pipeline.sh` 已內含 schema 部署（Phase 1），**不需要另外手動執行 `setup_schema.py`**。

```bash
# 完整初始化（Phase 1 部署 schema + Phase 2 同步 MSSQL + Phase 3 回填 silver/gold）
./scripts/etl/init_pipeline.sh

# 只部署 schema（例如重建環境時）
./scripts/etl/init_pipeline.sh --phase 1

# 只同步 bronze，指定月份
./scripts/etl/init_pipeline.sh --phase 2 --start 2026-04-01 --end 2026-04-30

# 只回填 silver/gold，指定月份
./scripts/etl/init_pipeline.sh --phase 3 --start 2026-04-01 --end 2026-04-30

# 逐月回填（依時間順序執行，每次換一組起訖）
./scripts/etl/init_pipeline.sh --phase 2,3 --start 2026-05-01 --end 2026-05-31
./scripts/etl/init_pipeline.sh --phase 2,3 --start 2026-06-01 --end 2026-06-30
```

`--phase` 支援逗號分隔組合，未指定時預設 `1,2,3`（完整流程）；`--start`/`--end` 同時驅動 Phase 2 的同步窗與 Phase 3 的回填窗。

### 3.4 日常排程——唯一入口 `daily_etl_wrapper.sh`

```bash
bash scripts/etl/daily_etl_wrapper.sh
```

內部固定執行順序（**順序不可調換**）：
1. `sync_unified_odbc.py --table all`——同步 bronze 至最新
2. `execute_etl.py --daily --low-ram`——自動計算增量範圍並回填 silver/gold

Step 1 必須先於 Step 2，因為 Step 2 的增量終點讀取 Step 1 剛寫入的 watermark；若順序顛倒或跳過 Step 1，Step 2 可能算不到最新資料。

排程設定（crontab，每日凌晨執行）：

```bash
0 0 * * * cd /path/to/dmp_flowable && bash scripts/etl/daily_etl_wrapper.sh >> /var/log/dmp_flowable/daily.log 2>&1
```

### 3.5 維運檢查指令

```bash
# 健康狀態儀表板（水位線、checkpoint、各表筆數）
python scripts/etl/execute_etl.py --status

# 手動同步單一表（不影響其他表）
python scripts/etl/sync_unified_odbc.py --table taskinst --start 2026-04-01 --end 2026-04-30

# 大量回填後，若某分區因重複同步而膨脹，逐分區去重（重寫資料，執行前需確認）
docker exec -it clickhouse-server-odbc clickhouse-client --query \
  "OPTIMIZE TABLE bronze.bpm_act_hi_varinst PARTITION 202604 FINAL"
```

### 3.6 常用查詢範本

**查詢 gold 層 KPI（Month 粒度範例，`FINAL` 不可省略）**：

```sql
SELECT
    period_key,
    sum(total_qty) AS total,
    sum(todo_qty)  AS todo,
    sum(doing_qty) AS doing,
    sum(done_qty)  AS done,
    floor(sum(done_qty) * 100 / sum(total_qty)) AS done_rate
FROM gold.rmv_l5_task_summary FINAL
WHERE period_type = 'Month'
  AND period_key  = '2026-04'
  AND region = 'CNE' AND plant = 'WJ2' AND vx_type = 'V2'
GROUP BY period_key;
```

**從 ClickHouse 查詢 MSSQL 來源表（唯讀，`odbc()` 語法）**：

```sql
SELECT * FROM odbc(
    'DSN=MSSQL_DSN;Database=<資料庫名>;Uid={MSSQL_USER};Pwd={MSSQL_PASSWORD};MARS_Connection=no',
    'dbo',
    '<表名>'
) LIMIT 10;
```

`Database=APP_SRV_BPM` 對應事實表（`ACT_HI_*`），`Database=APP_SRV_COMMON` 對應維度表（`HR_*`、`MDM_*`）。查大表務必加 `WHERE` 條件下推至 MSSQL 執行，避免全表掃描。
