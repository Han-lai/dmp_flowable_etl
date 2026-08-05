# DMP Flowable L5 指標系統參考文件

**版號**：v2.0（2026-08-05）

## 文件說明

本系統自 MSSQL（Flowable BPM 生產庫）透過 ODBC 擷取資料，於 ClickHouse 建立 bronze／silver／gold 三層數倉，並由 Cube.js 提供語義層查詢，產出 L5 任務完成率等製造 KPI。系統為生產運作中，每日排程自動增量。

本文的閱讀對象為第一次接手此系統的工程師。第 1 章說明系統組成，第 2 章定義各項指標的計算口徑，第 3 章說明資料管線的實作規則，第 4 章為部署與維運程序。

**全文適用之操作限制**：

- MSSQL 來源庫唯讀，嚴禁任何寫入或 DDL 操作。
- 連線資訊一律置於環境變數（`infra/.env`），程式碼不得寫死 IP 或密碼。
- `--reset`、`TRUNCATE`、`DROP`、`ALTER TABLE ... DELETE` 等破壞性操作執行前須確認影響範圍，本文已逐處標註。

---

## 1. 系統概觀

### 1.1 整體架構

```
┌──────────────────────┐
│  MSSQL（唯讀來源）      │
│  APP_SRV_BPM         │  Flowable 引擎事實表（任務／流程／變數）
│  APP_SRV_COMMON      │  HR／MDM 五階製造維度
└──────────┬───────────┘
           │ ODBC（Native C++ Bridge）
           ▼
┌─────────────────────────────────────────────┐
│  ClickHouse                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │  bronze  │──▶│  silver  │──▶│   gold   │ │
│  │ 原始鏡像  │   │ 清洗攤平  │   │  KPI彙總 │ │
│  └──────────┘   └──────────┘   └──────────┘ │
└────────────────────┬────────────────────────┘
                     ▼
              ┌─────────────┐
              │   Cube.js   │  語義層／預聚合
              └──────┬──────┘
                     ▼
              前端 BI／Superset
```

各服務以 split-stack 方式獨立部署，各自持有獨立的 `docker-compose.yml`，不共用生命週期。

### 1.2 模組職責

| 模組 | 職責 | 依賴 | 部署位置 |
|---|---|---|---|
| MSSQL `APP_SRV_BPM` | Flowable 引擎事實表：任務、流程實例、變數、身分關聯 | — | 既有生產環境，非本專案管理 |
| MSSQL `APP_SRV_COMMON` | HR 員工主檔、MDM 五階製造維度、權限對照 | — | 同上 |
| ETL 腳本群 `scripts/etl/` | Bronze 同步、Silver／Gold 運算、排程入口 | ClickHouse、MSSQL | 主機本地執行（非容器化） |
| ClickHouse + ODBC bridge | 三層數倉主體，含 MSSQL 連線橋接 | MSSQL（ODBC） | `infra/clickhouse/odbc/` |
| Cube.js | 語義層，唯讀查詢 `gold.rmv_l5_task_summary` | ClickHouse | `infra/cube/` |

ETL 腳本為資料流的唯一寫入端；Cube.js 對 ClickHouse 僅有讀取權限。

主力 KPI cube 為 `L5TaskPeriodic`（`cube/model/cubes/cube_l5_task_periodic.js`），資料源為 `gold.rmv_l5_task_summary`，提供 Day／Week／Month 三粒度的 total、todo、doing、done、acc 及費率 measures，供前端「7 天日趨勢 + 3 週對比 + 當月累計」視圖使用。所有 measures 直接對預聚合整數欄位執行 `SUM`，不在查詢時運算 Bitmap。

### 1.3 技術棧

| 項目 | 版本／規格 |
|---|---|
| ClickHouse | 25.8.18.1（客製 image，內建 Native ODBC，非官方原生映像） |
| ODBC 連線 | Native C++ ODBC Bridge（非 JDBC、非 Airbyte）。實測吞吐約 90,218 rows/s，為 JDBC 方案的 2.7 倍 |
| Python | 3.x；關鍵套件 `clickhouse-connect>=0.7.0`、`pyyaml>=6.0.0`、`pandas>=2.0.0` |
| Cube.js | 容器化部署，對外埠 4002／4003 |

---

## 2. 指標定義

本章定義 `gold.rmv_l5_task_summary` 各欄位的計算口徑。該表為 Cube.js 與所有報表查詢的唯一入口，查詢時必須加 `FINAL`（ReplacingMergeTree 特性，未加會讀到重複或舊版本列）。

### 2.1 指標一覽

每個期別（Day／Week／Month）× 五階維度組合輸出下列欄位：

| 欄位 | 定義 |
|---|---|
| `total_qty` | 該期別開單的任務總數（去重），等同 `bitmapOr(todo, doing, done)` |
| `todo_qty` | 結算點尚未被認領的任務數 |
| `doing_qty` | 結算點已認領但未完工的任務數 |
| `done_qty` | 結算點已完工的任務數 |
| `doing_done_qty` | `bitmapOr(doing, done)` 的去重結果，代表該期別有進度的任務 |
| `acc_qty` | 積壓量。各粒度口徑不同，見 2.4 節；與 `total_qty` 無大小關係 |
| `acc_total_qty` | 積壓率的分母：7 日滾動視窗內的總開單量 |

### 2.2 統計對象與結算點

**統計對象**：每筆任務永久錨定於其開單日（`task_start_date`），該日期即 `gold.rmv_l5_milestone_phys.snapshot_date`。任務不會因後續被認領或完成而移動至其他期別。

因此 Week 的統計對象為「該週**開單**的任務」，而非「該週有活動的任務」。例如一筆 2026-08-01（W31）開單、2026-08-20（W34）才認領的任務，僅出現於 W31，W34 的統計完全不含此任務。所有粒度的 `total_qty` 分母基準一致，皆為該期別的開單量。

> 例外：`< 2026-04-01` 的 Day 粒度採事件日語意，同一任務可能重複計入多天，詳見 2.6 節。

**結算點 T**：各粒度於下列單一時間點評估任務狀態。期間內的狀態變化不會逐日記錄，亦不取聯集。

| 粒度 | 結算點 T | SQL 運算式 |
|---|---|---|
| Day | 開單當天 | `task_start_date` 本身（判定用 `=` 比較） |
| Week | 開單日所屬 ISO 週的週日 | `toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY` |
| Month | 開單日所屬曆月的最後一日 | `toLastDayOfMonth(task_start_date)` |

**範例**：某任務於週一開單、週三認領、至週日仍未完工。Week 粒度的 T 為週日，該時點認領日已成立且尚未完工，故歸入 `doing_weekly`。此任務於週一、週二處於未認領狀態的事實不會被記錄，亦不計入 `todo_weekly`。

由此可知，`todo_weekly` 的語意為「**至週日仍未被認領**的任務數」，而非「本週曾出現未認領狀態的任務數」。同一任務不會同時計入兩種狀態。

### 2.3 狀態判定條件

以認領日（`task_claim_date`）、完工日（`task_end_date`）與結算點 T 比較，三種狀態互斥且窮盡：

| 狀態 | 判定條件 |
|---|---|
| `todo` | （認領日為空 **或** 認領日 > T）**且**（完工日為空 **或** 完工日 > T） |
| `doing` | 認領日不為空且 ≤ T **且**（完工日為空 **或** 完工日 > T） |
| `done` | 完工日不為空且 ≤ T |

**判定優先序**：`done` 僅取決於完工日，不檢查是否曾被認領。判讀時應先驗完工條件、再驗認領條件。若某任務認領日為空但完工日 ≤ T，系統歸類為 `done`。

Day 粒度（`>= 2026-04-01`）因 T 即開單當天，判定改用 `=` 而非 `<=`：認領日等於開單日才計入 `doing`，完工日等於開單日才計入 `done`。

### 2.4 acc 積壓量

`acc_qty` 與 todo／doing／done 為獨立指標，不代表三態中的任何一態，且各粒度口徑不同：

| 粒度 | 口徑 | 來源 |
|---|---|---|
| Day | 7 天滾動視窗：自開單日起連續 7 天，逐日檢查該任務是否仍未結案，未結案即計入當日 | `gold.rmv_l5_acc_phys` |
| Week／Month | 週期落後量：該期別 `todo_qty + doing_qty`（期末仍未完工者），與 7 天滾動無關 | `rmv_l5_task_completion_phys` 的 milestone bitmap 聯集 |

Day 粒度下，同一任務會計入其開單後 7 個不同日期的 `acc_qty`，此為設計行為。

### 2.5 費率規則（Rule 2）

全專案唯一標準：

```
rate = floor(qty * 100 / total)
```

一律無條件捨去，**禁止使用 `round()`**。兩者在邊界值上會得到不同百分比，與既有報表口徑不符將導致對帳失敗。

Day 粒度的 `accRate` 分母採 `acc_total_qty`（7 日滾動總開單量）而非當日開單量，以避免假日開單量趨近 0 時比率超過 100%。

### 2.6 版本邊界與粒度語意

Day 粒度須支援兩種統計口徑：歷史資料維持「事件日」語意，現行資料採「起始日 cohort」語意。因此同一張輸出表依時間邊界並存兩套計算邏輯：

| 粒度 | 邊界日期 | `< 邊界`（歷史邏輯） | `>= 邊界`（現行邏輯） |
|---|---|---|---|
| Day | `2026-04-01` | 事件日：開單／認領／完成任一發生即計入，同任務可能多天重複計入 | 起始日 cohort：僅計入開單當天，狀態於當下評估 |
| Week | `2026-03-30`（2026-W14 週一） | Cohort：`task_start_date` 為快照，狀態於週日評估 | 同左，公式一致 |
| Month | `2026-04-01` | Cohort：`task_start_date` 為快照，狀態於月底評估 | 同左，公式一致 |

**適用規則**：

- **Day 粒度不可跨邊界比較**。兩側語意不同，`2026-03-31` 與 `2026-04-01` 的 Day 數字口徑不一致。
- **Day 粒度同一任務會重複計入多天**（歷史邏輯的事件日語意下），故單月「逐日 total 加總」不等於「該月 Month total」。此為設計行為，非資料錯誤。
- **Week／Month 上界一律對齊期末**。回填 SQL 的 `WHERE` 上界使用 `toStartOfWeek(...) + INTERVAL 6 DAY` 或 `toLastDayOfMonth(...)`，而非原始輸入的 `{end_ts}`；不論 `--end` 落於期中何處，計算範圍都會延伸至該週或該月結束。
  - 此規則僅擴大「讀取 `rmv_l5_task_completion_phys` 的範圍」，不會重算上游 milestone bitmap。若 milestone 未涵蓋該期別，重跑 summary 只是將既有數值重新彙總一次。

### 2.7 已知限制：認領／完工過晚者，狀態不再更新

**影響範圍僅限 2.2 的狀態評估，不影響統計對象的歸屬。** 任務仍會正確留在其開單日所屬的期別，僅該期別內的 todo／doing／done 分類可能停留在較早的值。

成因：`backfill_gold_milestone.sql` 以 `task_start_date` 決定重算範圍，不檢查 `task_claim_date` 或 `task_end_date` 是否有異動；而 `--daily` 的計算視窗隨每日執行往前推移，開單日一旦落於視窗之外，該批任務即不再重算。此後發生的認領或完工雖會正確寫入 `silver.mv_fact_task_vx`（Silver 以 `START OR CLAIM OR END` 篩選，能捕捉異動），Gold milestone 不會再讀取。

| 粒度 | 受影響程度 |
|---|---|
| Day | 不受影響。T 即開單當天，判定僅需開單當日的事件，該日結束後的重算即可完整捕捉。 |
| Week／Month | 受影響。T 位於開單日之後數日至數週，期間發生的認領或完工若已在視窗滑過之後，依 2.3 應歸 `doing` 或 `done` 者會停留在 `todo`。Month 因 T 為月底、可容納的延遲最長，範圍最大。 |

視窗寬度取決於執行當下的 checkpoint 與 Bronze 水位線，非固定天數，須查 `ops_metrics.etl_checkpoint` 確認。

**修正方式**：對受影響的開單日重跑 `--backfill --start <開單日> --end <開單日>`。因 `rmv_l5_milestone_phys` 為 `AggregatingMergeTree`（bitmap 以 OR 合併，非覆寫），重跑前**必須先刪除該範圍既有列**，否則同一任務會殘留於新舊兩個狀態的 bitmap 中：

```sql
ALTER TABLE gold.rmv_l5_milestone_phys DELETE WHERE snapshot_date = '<開單日>';
```

---

## 3. 資料管線

### 3.1 計算階段

Bronze 層共 19 張表；Silver／Gold 層共 8 個計算階段，依序執行：

| 階段 | phase_id | 輸出表 | 職責 |
|---|---|---|---|
| 1 | `silver_varinst_pivoted` | `silver.mv_varinst_pivoted` | 將 EAV 格式的 `ACT_HI_VARINST` 攤平為寬表 |
| 2 | `silver_facts` | `silver.mv_fact_task_vx` | 核心任務事實表，含五階維度、`vx_type`、`is_excluded` 判定 |
| 3 | `silver_exclusion` | `silver.mv_fact_task_vx` | 更新自動完成任務的排除標記（UPDATE） |
| 4 | `gold_milestone` | `gold.rmv_l5_milestone_phys` | 里程碑指標（todo／doing／done bitmap） |
| 5 | `gold_acc` | `gold.rmv_l5_acc_phys` | 積壓指標，7 天滾動 bitmap |
| 6 | `gold_unified` | `gold.rmv_l5_task_completion_phys` | 合併 milestone 與 acc |
| 7 | `gold_summary_historical` | `gold.rmv_l5_task_summary` | 歷史邏輯管線，處理 `< 2026-04-01` |
| 8 | `gold_summary` | `gold.rmv_l5_task_summary` | 現行邏輯管線，處理 `>= 2026-04-01` |

### 3.2 Bronze 層同步策略

**full 策略（15 張維度表）**：HR、MDM 五階、權限對照等。不吃時間窗，每次整批重抓。

同步流程為建暫存表 → INSERT → 驗證列數大於 0 → 原子替換（RENAME 舊表、RENAME 新表、DROP 舊表）。此流程為非破壞性：密碼錯誤或連線失敗時原表不受影響，僅該次同步失敗。

**batch 策略（4 張事實表）**：`taskinst`、`varinst`、`procinst`、`identitylink`。依 `time_col` 切時間窗批次同步，透過 `_sync_watermark` 記錄進度以支援續跑。

所有事實表皆為 `ReplacingMergeTree`，`PARTITION BY toYYYYMM(時間欄)`，`TTL` 保留 1 年。超過一年的資料由 ClickHouse 自動清除，無法自 bronze 還原，須重新自 MSSQL 拉取（前提是來源仍保留）。

### 3.3 Watermark 與續跑

`bronze._sync_watermark`（`ReplacingMergeTree`，每張表僅保留最新一列）記錄三個獨立欄位：

| 欄位 | 語意 | 寫入時機 |
|---|---|---|
| `sync_time` | 該次同步實際執行的時間（wall clock） | 每次同步寫入 `now()` |
| `last_sync_time` | 該次同步的時間窗結尾（batch 表）或執行時間（full 表） | 每個批次無條件寫入，含 0 筆批次 |
| `max_data_time` | 該表實體資料目前的最大時間，自物理表現查 | 僅在批次有寫入資料時重查 |

**續跑點判斷**（`get_last_watermark()`）優先取 `max_data_time`。即使 `last_sync_time` 因手動指定過去的 `--end` 而被回撥，亦不影響下次自動續跑的起點。

`--daily` 模式判斷增量終點時改讀 `last_sync_time`。若該值被回撥且未先執行一次正常同步即直接跑 `--daily`，將計算不到最新資料。正常排程流程（先 sync 後 daily）不會觸發此問題，因 sync 必定先將 `last_sync_time` 寫回正確值。

**去重語意**：`bpm_act_hi_varinst` 排序鍵為 `(PROC_INST_ID_, NAME_, CREATE_TIME_)`、`bpm_act_hi_identitylink` 為 `(TASK_ID_, USER_ID_, TYPE_)`，皆非 MSSQL 主鍵，同鍵多列會被去重合併為一列。因此 bronze 筆數低於 MSSQL 原始筆數屬正常行為，非同步遺漏。`taskinst` 與 `procinst` 的排序鍵即為唯一鍵，兩端筆數完全一致，可作為對帳基準。

### 3.4 Silver 層排除邏輯

任務符合下列任一條件即標記 `is_excluded`，不計入 KPI：

| 條件 | `exclude_reason` |
|---|---|
| 變數 `autoComplete=1` | `bypass` |
| 執行人為 `SYSTEM` 帳號 | `system_bypass` |
| `TASK_DEF_KEY_` 以 `E` 或 `C` 開頭（系統節點） | `system_node` |
| 工單號以 `Q` 或 `R` 開頭（測試單） | `Q_order` / `R_order` |
| 任務名稱含 `Notify` 或 `Dummy`（通知／虛擬任務） | — |

其中 `autoComplete_flag` 另由 `backfill_exclusion.sql`（階段 3）以 `ALTER TABLE ... UPDATE` 更新，涵蓋首次計算時 `ACT_HI_VARINST` 尚未寫入 `autoComplete` 變數的任務。

### 3.5 自適應切窗

Bronze 同步（`sync_batch_adaptive()`）與 Silver／Gold 運算（`run_safe()`）皆內建自動切窗重試。遇負載過高或 ClickHouse OOM（`Memory limit exceeded`、`Code: 241`）時，將該時間區間對半切分後遞迴重試，以降低單次查詢對 MSSQL 與 ClickHouse 的瞬間負載。此機制自動觸發，無需人工設定。

### 3.6 新增或調整同步表

Bronze 同步表清單定義於 `scripts/etl/config/sync_tables.yaml`，每張表一個區塊：

```yaml
<table_key>:
  source: "<MSSQL_DB>.dbo.<來源表名>"     # 例：APP_SRV_COMMON.dbo.HR_Employee_0503
  target: "bronze.<目標表名>"             # 例：bronze.common_hr_employee
  strategy: "full" | "batch"
  engine_ddl: "<明確欄位型別宣告>"          # 必填
  columns: "<SELECT 欄位清單>"             # 可用 "*" 或明確列出（可含轉換運算式）

  # 以下僅 strategy: batch 需要
  time_col: "<時間欄位>"                   # 切分時間窗依據，例如 START_TIME_
  step_days: 2                            # 每批次天數
  history_start: "2025-10-01"             # 無 watermark 時的起始回填日期
```

新增一張表需完成兩個步驟，缺一不可：

1. **於 `sync_tables.yaml` 新增區塊**。`engine_ddl` 必須明確宣告每個欄位型別，不可省略或以 `SELECT *` 推斷取代，目的是繞過 ODBC driver 對 LOB（`varchar(max)`、`xml`）欄位自動探測時的死鎖問題。

2. **於對應 schema DDL 檔新增 `CREATE TABLE IF NOT EXISTS bronze.<目標表名>`**。Flowable 核心表加於 `sql/etl/schema/01_bronze_flowable_core.sql`，MSSQL COMMON 維度表加於 `sql/etl/schema/02_bronze_common_dims.sql`，新增後執行 `init_pipeline.sh --phase 1` 部署。目標表必須先存在於 ClickHouse——`sync_full()` 是以 `CREATE TABLE temp AS target` 複製既有目標表結構建暫存表，目標表不存在會直接失敗。

兩步驟完成後，`sync_unified_odbc.py --table all` 會自動掃描 `sync_tables.yaml` 所有區塊逐一同步，無需修改 Python 程式碼。調整既有表的抓取欄位或時間窗策略，同樣只需修改 YAML。

---

## 4. 部署與維運

部署順序為：先啟動 ClickHouse，執行 `init_pipeline.sh` 將 MSSQL 資料拉取進 Bronze 並運算出 Silver／Gold，確認資料到位後再啟動 Cube.js 對外提供查詢。

所有連線資訊來自 `infra/.env`，執行前須先載入：

```bash
cd /path/to/dmp_flowable
set -a && . infra/.env && set +a
```

### 4.1 環境變數

`infra/.env`（版控外，需自行建立）：

```bash
VOLUMES_ROOT=/data/dmp_flowable          # docker volume 掛載根目錄
CLICKHOUSE_HOST=<ClickHouse 主機 IP>
CLICKHOUSE_PORT=8123
CLICKHOUSE_USERNAME=default
CLICKHOUSE_PASSWORD=<ClickHouse 密碼>
CUBEJS_API_SECRET=<Cube.js API 密鑰>
```

執行 Phase 2（MSSQL 同步）另需：

```bash
export MSSQL_USER=APP_SRV_BPM
export MSSQL_PASSWORD=<MSSQL 密碼>       # 留空將導致同步失敗（fail-loud，不會清空資料）
export ODBC_DSN=MSSQL_DSN                # 預設值，通常無需覆寫
```

### 4.2 服務啟動

```bash
# ClickHouse + ODBC bridge（資料倉儲主體）
docker-compose -f infra/clickhouse/odbc/docker-compose-odbc.yml up -d

# Cube.js（語義層，對外埠 4002／4003）
docker-compose -f infra/cube/docker-compose.yml up -d
```

### 4.3 初次建置

`init_pipeline.sh` 為唯一入口，已內含 schema 部署（Phase 1），不需另外手動執行 `setup_schema.py`。

```bash
# 完整初始化（Phase 1 schema + Phase 2 同步 + Phase 3 回填）
./scripts/etl/init_pipeline.sh

# 只部署 schema（例如重建環境）
./scripts/etl/init_pipeline.sh --phase 1

# 只同步 bronze，指定月份
./scripts/etl/init_pipeline.sh --phase 2 --start 2026-04-01 --end 2026-04-30

# 只回填 silver/gold，指定月份
./scripts/etl/init_pipeline.sh --phase 3 --start 2026-04-01 --end 2026-04-30

# 逐月回填（依時間順序執行，每次換一組起訖）
./scripts/etl/init_pipeline.sh --phase 2,3 --start 2026-05-01 --end 2026-05-31
./scripts/etl/init_pipeline.sh --phase 2,3 --start 2026-06-01 --end 2026-06-30
```

`--phase` 支援逗號分隔組合，未指定時預設 `1,2,3`。`--start` 與 `--end` 同時驅動 Phase 2 的同步窗與 Phase 3 的回填窗。

### 4.4 日常排程

`daily_etl_wrapper.sh` 為唯一入口：

```bash
bash scripts/etl/daily_etl_wrapper.sh
```

內部執行順序固定，不可調換：

1. `sync_unified_odbc.py --table all`——同步 bronze 至最新
2. `execute_etl.py --daily --low-ram`——自動計算增量範圍並回填 silver／gold

步驟 1 必須先於步驟 2，因步驟 2 的增量終點讀取步驟 1 剛寫入的 watermark。順序顛倒或跳過步驟 1，將導致計算不到最新資料。

crontab 設定（每日凌晨執行）：

```bash
0 0 * * * cd /path/to/dmp_flowable && bash scripts/etl/daily_etl_wrapper.sh >> /var/log/dmp_flowable/daily.log 2>&1
```

### 4.5 維運檢查

```bash
# 健康狀態儀表板（水位線、checkpoint、各表筆數）
python scripts/etl/execute_etl.py --status

# 手動同步單一表（不影響其他表）
python scripts/etl/sync_unified_odbc.py --table taskinst --start 2026-04-01 --end 2026-04-30

# 大量回填後若某分區因重複同步而膨脹，逐分區去重（重寫資料，執行前需確認）
docker exec -it clickhouse-server-odbc clickhouse-client --query \
  "OPTIMIZE TABLE bronze.bpm_act_hi_varinst PARTITION 202604 FINAL"
```

### 4.6 常用查詢

**查詢 gold 層 KPI**（Month 粒度範例，`FINAL` 不可省略）：

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

**自 ClickHouse 查詢 MSSQL 來源表**（唯讀，`odbc()` 語法）：

```sql
SELECT * FROM odbc(
    'DSN=MSSQL_DSN;Database=<資料庫名>;Uid={MSSQL_USER};Pwd={MSSQL_PASSWORD};MARS_Connection=no',
    'dbo',
    '<表名>'
) LIMIT 10;
```

`Database=APP_SRV_BPM` 對應事實表（`ACT_HI_*`），`Database=APP_SRV_COMMON` 對應維度表（`HR_*`、`MDM_*`）。查詢大表務必加 `WHERE` 條件下推至 MSSQL 執行，避免全表掃描。
