# MSSQL → ClickHouse 端到端資料同步工作流

> 文件版本: 1.0  
> 最後更新: 2026-01-13  
> 專案: DMP Flowable 資料同步

---

## 1. Overview

### 1.1 文件目的

本文件記錄 DMP Flowable 專案從 MSSQL 同步資料到 ClickHouse，並建立 Bronze / Silver / Gold 分層資料模型，最終串接 Cube.js 語意層的完整工作流。

本文件定位為：
- 工程師實作依據（可照文件從零部署）
- 架構設計與工具選型說明
- 維運、回補、效能優化的參考依據

### 1.2 適用範圍

- 資料來源：MSSQL Server（APP_SRV_BPM + APP_SRV_COMMON）
- 資料目標：ClickHouse
- 資料模型：Bronze → Silver → Gold
- 語意層：Cube.js
- 同步方式：JDBC Bridge

### 1.3 Non-goals（不處理的事項）

- CDC (Change Data Capture)：MSSQL 未啟用 CDC，本專案不使用
- 即時串流同步：本專案採用批次同步，非即時
- 多租戶隔離：目前為單一租戶架構
- 資料加密傳輸：內網環境，未啟用 SSL
- 自動化排程：目前手動執行，排程需外部工具（cron / Airflow）

---

## 2. Overall Architecture

### 2.1 元件說明

| 元件 | 角色 | 部署位置 | 版本 |
|------|------|----------|------|
| MSSQL Server | 資料來源 | 10.136.158.140:1433 | SQL Server |
| ClickHouse | 資料倉儲 | REDACTED_IP:8121 | 24.3+ |
| JDBC Bridge | 跨資料庫查詢 | 同 ClickHouse 主機 | 2.1.0 |
| Python Scripts | ETL 控制 | 本機執行 | Python 3.x |
| Cube.js | 語意層 | Docker (localhost:4002/4003) | latest |

### 2.2 高層資料流圖

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              MSSQL                                      │
│  APP_SRV_BPM (5 張表)  +  APP_SRV_COMMON (11 張表)                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                              JDBC Bridge
                         (sync/sync_incremental.py)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Bronze Layer (16 張表)                          │
│  ReplacingMergeTree (大表增量) + MergeTree (小表全量)                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
         ┌─────────────────────┐       ┌─────────────────────┐
         │   Silver View (4)   │       │   Silver RMV (4)    │
         │   (即時查詢)         │       │   (每日刷新)         │
         └─────────────────────┘       └─────────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
                    ┌─────────────────────────────────┐
                    │      Gold Layer (2 張表)        │
                    │   (每日快照，手動執行)           │
                    └─────────────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────┐
                    │         Cube.js (5 Cubes)       │
                    │   REST API: localhost:4002      │
                    │   Playground: localhost:4003    │
                    └─────────────────────────────────┘
```

---

## 3. End-to-End Data Flow

### 3.1 完整資料流程

```
Step 1: Bronze 同步 (手動)
┌──────────────────────────────────────────────────────────────────────┐
│  python sync/sync_incremental.py all                                 │
│                                                                      │
│  ┌─────────────┐    JDBC Bridge    ┌─────────────────────────────┐  │
│  │   MSSQL     │ ───────────────► │   Bronze (ClickHouse)        │  │
│  │  16 張表    │                   │   16 張表                    │  │
│  └─────────────┘                   │   - 5 張增量 (Watermark)     │  │
│                                    │   - 11 張全量 (DROP+CREATE)  │  │
│                                    └─────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 2: Silver RMV 刷新 (自動)
┌──────────────────────────────────────────────────────────────────────┐
│  ClickHouse 自動排程: REFRESH EVERY 1 DAY (02:00 UTC = 10:00 TPE)    │
│                                                                      │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐  │
│  │   Bronze Tables             │ ──►│   Silver RMV (4 張)         │  │
│  │   (原始資料)                 │    │   - RMV_PROC_VARIABLES      │  │
│  │                             │    │   - RMV_HI_PROC_TASK_NODE   │  │
│  │                             │    │   - RMV_HI_PROCINST_NODE    │  │
│  │                             │    │   - RMV_HI_BIZ_EVENT_INFO   │  │
│  └─────────────────────────────┘    └─────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 3: Gold 快照 (手動)
┌──────────────────────────────────────────────────────────────────────┐
│  python scripts/create_gold_snapshot.py                              │
│                                                                      │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐  │
│  │   Silver RMV                │ ──►│   Gold Tables (2 張)        │  │
│  │   (預計算資料)               │    │   - DAILY_METRICS_SNAPSHOT  │  │
│  │                             │    │   - DAILY_BIZ_EVENT_SNAPSHOT│  │
│  └─────────────────────────────┘    └─────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 4: Cube.js 查詢 (即時)
┌──────────────────────────────────────────────────────────────────────┐
│  Cube.js 讀取 Silver RMV + Gold Tables                               │
│                                                                      │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐  │
│  │   Silver RMV (即時指標)      │ ──►│   Cube.js REST API          │  │
│  │   Gold Tables (歷史趨勢)     │    │   localhost:4002            │  │
│  └─────────────────────────────┘    └─────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 Full Refresh vs Incremental 在流程中的位置

| 層級 | 刷新策略 | 觸發方式 | 說明 |
|------|----------|----------|------|
| Bronze (大表 5 張) | Incremental | 手動 | Watermark 追蹤，INSERT 增量 |
| Bronze (小表 11 張) | Full Refresh | 手動 | DROP + CREATE TABLE AS SELECT |
| Silver RMV | Full Refresh | 自動 (每日) | ClickHouse 自動刷新整張表 |
| Gold | Full Refresh | 手動 | INSERT 當日快照，ReplacingMergeTree 去重 |

### 3.3 建議執行時間線

```
09:00  執行 Bronze 同步 (python sync/sync_incremental.py all)
10:00  RMV 自動刷新完成 (02:00 UTC)
10:30  執行 Gold 快照 (python scripts/create_gold_snapshot.py)
       ↓
       Cube.js API 可查詢最新資料
```

---

## 4. MSSQL → ClickHouse Ingestion 設計

### 4.1 JDBC 連線與安全

**連線設定**

```json
// docker/jdbc-bridge/config/datasources/mssql_master.json
{
  "mssql_master": {
    "driverUrls": ["https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/7.4.1.jre8/mssql-jdbc-7.4.1.jre8.jar"],
    "driverClassName": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
    "jdbcUrl": "jdbc:sqlserver://10.136.158.140:1433;databaseName=master;encrypt=false;trustServerCertificate=true",
    "username": "DMP_APP_SRV",
    "password": "APP@DB#01"
  }
}
```

**帳號權限**
- 帳號：DMP_APP_SRV
- 權限：Read-only（SELECT 權限）
- 可存取資料庫：APP_SRV_BPM, APP_SRV_COMMON

**網路假設**
- 內網環境，ClickHouse 與 MSSQL 可直接連線
- 未啟用 SSL 加密（encrypt=false）
- 使用 IP 而非 hostname（避免 DNS 解析問題）

**JDBC Driver 版本**
- 使用 7.4.1.jre8（較新版本 12.x 連線失敗）
- 原因：JDBC Bridge 2.1.0 與新版 Driver 相容性問題

### 4.2 Full Refresh 與 Incremental 的雙模式設計

#### A. Full Refresh（全量重刷）

**適用情境**
- 小表（資料量 < 10,000 筆）
- 設定表、維度表
- Schema 變更後需重建
- 歷史資料重建

**本專案使用 Full Refresh 的表（11 張）**

| 表名 | 資料量 | 原因 |
|------|--------|------|
| ACT_RE_PROCDEF | ~100 | 流程定義，變動少 |
| HR_Employee | ~5,000 | 員工資料，無追蹤欄位 |
| ProcessRoleUserMapping | ~1,000 | 設定表 |
| ProcessRoleGroup | ~50 | 設定表 |
| ProcessRoleGroupMapping | ~100 | 設定表 |
| EmpNodeRoleMapping | ~500 | 設定表 |
| EmpOrgInfoMapping | ~5,000 | 設定表 |
| EmpUserGroupMapping | ~1,000 | 設定表 |
| UserGroup | ~50 | 設定表 |
| DMPFunctionConfig | ~100 | 設定表 |
| DMPFunctionClientMapping | ~50 | 設定表 |

**End-to-end 流程**

```
1. DROP TABLE IF EXISTS bronze.{target_table}
2. CREATE TABLE {target_table} ENGINE = MergeTree() ORDER BY tuple()
   AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM {source_table}')
3. 驗證 row count
```

**SQL 範例**

```sql
-- Full Refresh 範例：HR_Employee
DROP TABLE IF EXISTS bronze.common_hr_employee;

CREATE TABLE bronze.common_hr_employee
ENGINE = MergeTree()
ORDER BY tuple()
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_COMMON.dbo.HR_Employee');

-- 驗證
SELECT count(*) FROM bronze.common_hr_employee;
```

**Python 實作**

```python
# sync/sync_incremental.py - sync_full()
def sync_full(client, config: dict) -> SyncResult:
    source = config["source"]
    target = config["target"]
    
    client.command(f"DROP TABLE IF EXISTS {target}")
    
    sql = f"""
    CREATE TABLE {target} 
    ENGINE = MergeTree() 
    ORDER BY tuple() 
    AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM {source}')
    """
    client.command(sql)
    
    row_count = client.command(f"SELECT count(*) FROM {target}")
    return SyncResult(step=target, row_count=row_count, sync_type="full")
```

**風險與成本評估**
- 風險：同步期間表不可用（DROP 後到 CREATE 完成前）
- 成本：每次全量傳輸，網路流量較大
- 緩解：小表資料量小，同步時間 < 5 秒

**回補與重跑策略**
- 直接重新執行即可（DROP + CREATE 天然冪等）
- 無需額外處理

#### B. Incremental（增量同步）

**適用條件**
- 表有可靠的追蹤欄位（timestamp 或自增 ID）
- 資料量大（> 10,000 筆）
- 資料只新增或更新，不刪除

**本專案使用 Incremental 的表（5 張）**

| 表名 | 資料量 | 追蹤欄位 | 主鍵 |
|------|--------|----------|------|
| ACT_HI_PROCINST | ~17,000 | START_TIME_ | ID_ |
| ACT_HI_TASKINST | ~50,000 | LAST_UPDATED_TIME_ | ID_ |
| ACT_HI_IDENTITYLINK | ~600,000 | CREATE_TIME_ | ID_ |
| ACT_HI_VARINST | ~660,000 | LAST_UPDATED_TIME_ | ID_ |
| FlowableTaskStats | ~1,300,000 | LastUpdatedTime | tuple() |

**增量策略：Timestamp Watermark**

本專案採用 timestamp watermark 策略：
- 記錄上次同步的最大時間戳
- 下次同步只拉取 > watermark 的資料
- 使用 ReplacingMergeTree 處理重複

**Watermark 狀態表設計**

```sql
-- bronze._sync_watermark
CREATE TABLE IF NOT EXISTS bronze._sync_watermark (
    table_name String,           -- 表名
    last_sync_time DateTime64(3), -- 上次同步的最大時間戳
    sync_time DateTime64(3),      -- 本次同步時間
    row_count UInt64              -- 本次同步筆數
) ENGINE = ReplacingMergeTree(sync_time)
ORDER BY (table_name);
```

**去重與冪等（Idempotency）**

使用 ReplacingMergeTree + _sync_time 版本欄位：

```sql
CREATE TABLE bronze.bpm_act_hi_taskinst
ENGINE = ReplacingMergeTree(_sync_time)
ORDER BY (ID_)
AS SELECT *, now64(3) as _sync_time 
FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST');
```

- 相同 ORDER BY 的資料，保留 _sync_time 最大的版本
- 查詢時使用 FINAL 關鍵字取得去重後結果
- 或定期執行 OPTIMIZE TABLE ... FINAL 強制合併

**Incremental 同步流程**

```
1. 檢查目標表是否存在
   ├─ 不存在 → 首次同步（CREATE TABLE AS SELECT 全量）
   └─ 存在 → 增量同步
       │
       ├─ 2. 讀取 Watermark (上次同步時間)
       │
       ├─ 3. 從 MSSQL 拉取增量資料
       │     SELECT * FROM {source} WHERE {tracking_col} > '{watermark}'
       │
       ├─ 4. INSERT INTO ClickHouse (ReplacingMergeTree 處理重複)
       │
       └─ 5. 更新 Watermark
```

**SQL 範例**

```sql
-- 增量同步範例：ACT_HI_TASKINST
-- Step 1: 讀取 watermark
SELECT last_sync_time 
FROM bronze._sync_watermark FINAL
WHERE table_name = 'bronze.bpm_act_hi_taskinst';
-- 假設結果: 2026-01-12 10:00:00.000

-- Step 2: 拉取增量資料並插入
INSERT INTO bronze.bpm_act_hi_taskinst
SELECT *, now64(3) as _sync_time
FROM jdbc('mssql_master', '
    SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST
    WHERE LAST_UPDATED_TIME_ > CONVERT(datetime2, ''2026-01-12 10:00:00.000'', 121)
');

-- Step 3: 更新 watermark
INSERT INTO bronze._sync_watermark (table_name, last_sync_time, sync_time, row_count)
SELECT 
    'bronze.bpm_act_hi_taskinst',
    max(LAST_UPDATED_TIME_),
    now64(3),
    count(*)
FROM jdbc('mssql_master', '
    SELECT LAST_UPDATED_TIME_ FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST
    WHERE LAST_UPDATED_TIME_ > CONVERT(datetime2, ''2026-01-12 10:00:00.000'', 121)
');
```

**Python 實作**

```python
# sync/sync_incremental.py - sync_incremental()
def sync_incremental(client, config: dict) -> SyncResult:
    source = config["source"]
    target = config["target"]
    pk = config["primary_key"]
    tracking_col = config["tracking_col"]
    
    # 檢查表是否存在
    table_exists = check_table_exists(client, target)
    
    if not table_exists:
        # 首次同步：建立表並全量載入
        create_sql = f"""
        CREATE TABLE {target}
        ENGINE = ReplacingMergeTree(_sync_time)
        ORDER BY ({pk})
        AS SELECT *, now64(3) as _sync_time 
        FROM jdbc('mssql_master', 'SELECT * FROM {source}')
        """
        client.command(create_sql)
        # 設定初始 watermark
        max_tracking = get_max_tracking_value(client, source, tracking_col)
        update_watermark(client, target, max_tracking, row_count)
        return SyncResult(sync_type="initial")
    
    # 增量同步
    watermark = get_watermark(client, target)
    
    insert_sql = f"""
    INSERT INTO {target}
    SELECT *, now64(3) as _sync_time
    FROM jdbc('mssql_master', '
        SELECT * FROM {source}
        WHERE {tracking_col} > CONVERT(datetime2, ''{watermark}'', 121)
    ')
    """
    client.command(insert_sql)
    
    # 更新 watermark
    new_max = get_max_tracking_value(client, source, tracking_col)
    update_watermark(client, target, new_max, row_count)
    
    return SyncResult(sync_type="incremental")
```

**Late-arriving / 更新資料處理**

本專案的處理方式：
- 使用 LAST_UPDATED_TIME_ 作為追蹤欄位（而非 CREATE_TIME_）
- 資料更新時 LAST_UPDATED_TIME_ 會變動，會被增量同步抓到
- ReplacingMergeTree 會保留最新版本

**限制**：
- 如果 MSSQL 資料被刪除，ClickHouse 不會同步刪除
- 本專案的 Flowable 歷史表不會刪除資料，故不影響

**驗收查核**

```sql
-- 檢查 watermark 單調性
SELECT 
    table_name,
    last_sync_time,
    sync_time,
    row_count
FROM bronze._sync_watermark FINAL
ORDER BY table_name;

-- 檢查資料筆數
SELECT 
    'MSSQL' as source,
    count(*) as cnt
FROM jdbc('mssql_master', 'SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST')
UNION ALL
SELECT 
    'ClickHouse' as source,
    count(*) as cnt
FROM bronze.bpm_act_hi_taskinst FINAL;
```

#### C. Full vs Incremental 的排程與切換

**使用情境決策準則**

| 條件 | 建議策略 |
|------|----------|
| 資料量 < 10,000 筆 | Full Refresh |
| 無可靠追蹤欄位 | Full Refresh |
| 資料量 > 10,000 筆 + 有追蹤欄位 | Incremental |
| Schema 變更 | Full Refresh (重建) |
| 資料品質問題需重建 | Full Refresh |

**執行模式參數化**

```bash
# 全部同步（增量 + 全量）
python sync/sync_incremental.py all

# 只同步增量表
python sync/sync_incremental.py incremental

# 只同步全量表
python sync/sync_incremental.py full
```

**Backfill 策略**

1. **Incremental Backfill（補區間）**
   - 手動調整 watermark 到需要回補的時間點
   - 重新執行增量同步

```sql
-- 回補範例：將 watermark 調回 7 天前
INSERT INTO bronze._sync_watermark (table_name, last_sync_time, sync_time, row_count)
VALUES ('bronze.bpm_act_hi_taskinst', 
        now64(3) - INTERVAL 7 DAY, 
        now64(3), 
        0);
```

2. **Full Refresh Backfill（重刷表）**
   - 刪除目標表
   - 重新執行首次同步

```bash
# 刪除表後重新同步
python -c "
import clickhouse_connect
client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121)
client.command('DROP TABLE IF EXISTS bronze.bpm_act_hi_taskinst')
"
python sync/sync_incremental.py incremental
```

---

## 5. Bronze Layer（Raw Data）

### 5.1 設計原則

- **Append-only**：增量同步只 INSERT，不 UPDATE/DELETE
- **保留來源欄位**：完整保留 MSSQL 原始欄位，不做轉換
- **Metadata 欄位**：加入 _sync_time 追蹤同步時間

### 5.2 ClickHouse Engine 選擇

| 表類型 | Engine | 原因 |
|--------|--------|------|
| 大表（增量） | ReplacingMergeTree | 支援去重，處理重複資料 |
| 小表（全量） | MergeTree | 簡單，無需去重 |

### 5.3 命名規則

```
bronze.{source_db}_{table_name}

範例：
- bronze.bpm_act_hi_procinst      (來自 APP_SRV_BPM.ACT_HI_PROCINST)
- bronze.common_hr_employee       (來自 APP_SRV_COMMON.HR_Employee)
```

### 5.4 DDL 範例

**增量表（ReplacingMergeTree）**

```sql
-- Bronze 表：ACT_HI_TASKINST（任務實例歷史）
CREATE TABLE IF NOT EXISTS bronze.bpm_act_hi_taskinst
(
    ID_ String,
    REV_ Nullable(Int32),
    PROC_DEF_ID_ Nullable(String),
    TASK_DEF_ID_ Nullable(String),
    TASK_DEF_KEY_ Nullable(String),
    PROC_INST_ID_ Nullable(String),
    EXECUTION_ID_ Nullable(String),
    NAME_ Nullable(String),
    ASSIGNEE_ Nullable(String),
    START_TIME_ DateTime,
    CLAIM_TIME_ Nullable(DateTime),
    END_TIME_ Nullable(DateTime),
    DURATION_ Nullable(Decimal(38, 0)),
    DELETE_REASON_ Nullable(String),
    PRIORITY_ Nullable(Int32),
    DUE_DATE_ Nullable(DateTime),
    LAST_UPDATED_TIME_ Nullable(DateTime64(7)),
    -- 同步 metadata
    _sync_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_sync_time)
PARTITION BY toYYYYMM(START_TIME_)
ORDER BY (PROC_INST_ID_, START_TIME_, ID_)
SETTINGS index_granularity = 8192;
```

**全量表（MergeTree）**

```sql
-- Bronze 表：HR_Employee（員工資料）
CREATE TABLE IF NOT EXISTS bronze.common_hr_employee
(
    EmpCode String,
    EmpName Nullable(String),
    DeptCode Nullable(String),
    DeptCodeLname Nullable(String),
    -- ... 其他欄位
)
ENGINE = MergeTree()
ORDER BY tuple()
SETTINGS index_granularity = 8192;
```

### 5.5 Bronze 表清單

| 表名 | 來源 | Engine | 資料量 | 用途 |
|------|------|--------|--------|------|
| bpm_act_hi_procinst | APP_SRV_BPM | ReplacingMergeTree | ~17K | 流程實例歷史 |
| bpm_act_hi_taskinst | APP_SRV_BPM | ReplacingMergeTree | ~50K | 任務實例歷史 |
| bpm_act_hi_identitylink | APP_SRV_BPM | ReplacingMergeTree | ~600K | 任務參與者 |
| bpm_act_hi_varinst | APP_SRV_BPM | ReplacingMergeTree | ~660K | 流程變數 |
| bpm_act_re_procdef | APP_SRV_BPM | MergeTree | ~100 | 流程定義 |
| common_flowable_task_stats | APP_SRV_COMMON | ReplacingMergeTree | ~1.3M | 任務統計 |
| common_hr_employee | APP_SRV_COMMON | MergeTree | ~5K | 員工資料 |
| common_process_role_* | APP_SRV_COMMON | MergeTree | <1K | 角色設定 |
| common_emp_* | APP_SRV_COMMON | MergeTree | <5K | 員工對應 |
| common_user_group | APP_SRV_COMMON | MergeTree | <100 | 使用者群組 |
| common_dmp_function_* | APP_SRV_COMMON | MergeTree | <100 | 功能設定 |

---

## 6. Silver Layer（Clean / Conformed）

### 6.1 設計原則

- **清洗與標準化**：統一欄位命名、處理 NULL 值
- **派生欄位**：計算 TASK_STATUS、時長等
- **樞紐化**：將 EAV 格式轉為寬表
- **JOIN 整合**：整合多張 Bronze 表

### 6.2 View vs Materialized View 的取捨

本專案同時建立 View 和 RMV（Refreshable Materialized View）：

| 類型 | 用途 | 優點 | 缺點 |
|------|------|------|------|
| View (V_*) | 即時查詢 | 資料最新 | 效能慢（每次重算） |
| RMV (RMV_*) | 報表查詢 | 效能快 4-10x | 資料延遲 ≤24h |

**效能比較（實測）**

| 查詢 | View (ms) | RMV (ms) | 加速比 |
|------|-----------|----------|--------|
| 在途任務總數 | 147 | 15 | 10.1x |
| TASK_STATUS 分布 | 123 | 14 | 9.1x |
| 在途任務-依廠區 | 110 | 12 | 9.2x |
| 自動完成率 | 95 | 11 | 8.6x |

**建議**：
- Cube.js 預設讀取 RMV（效能優先）
- 需要即時資料時，可改用 View

### 6.3 Silver View 清單

| View | Grain | 用途 |
|------|-------|------|
| V_PROC_VARIABLES_PIVOTED | PROC_INST_ID | 流程變數樞紐化 |
| V_TASK_VARIABLES_PIVOTED | TASK_ID | 任務變數樞紐化 |
| V_HI_PROC_TASK_NODE | TASK_ID | 任務節點層 |
| V_HI_PROCINST_NODE | PROC_INST_ID | 流程實例層 |
| V_HI_BIZ_EVENT_INFO | BUSINESS_KEY | 業務事件層 |

### 6.4 關鍵轉換邏輯

**流程變數樞紐化（EAV → 寬表）**

```sql
-- V_PROC_VARIABLES_PIVOTED
SELECT
    PROC_INST_ID_ AS PROC_INST_ID,
    anyIf(TEXT_, NAME_ = 'plant') AS PLANT,
    anyIf(TEXT_, NAME_ = 'factory') AS FACTORY,
    anyIf(TEXT_, NAME_ = 'region') AS REGION,
    anyIf(TEXT_, NAME_ = 'lineName') AS LINE_NAME,
    anyIf(TEXT_, NAME_ = 'modelName') AS MODEL_NAME
FROM bronze.bpm_act_hi_varinst
WHERE NAME_ IN ('plant', 'factory', 'region', 'lineName', 'modelName')
  AND PROC_INST_ID_ IS NOT NULL
  AND TASK_ID_ IS NULL
GROUP BY PROC_INST_ID_;
```

**TASK_STATUS 判斷邏輯**

```sql
multiIf(
    DELETE_REASON_ IS NOT NULL AND DELETE_REASON_ != '', 'CANCELLED',
    ASSIGNEE_ IS NULL AND END_TIME_ IS NULL, 'TODO',
    ASSIGNEE_ IS NOT NULL AND END_TIME_ IS NULL, 'DOING',
    ASSIGNEE_ IS NOT NULL AND CLAIM_TIME_ IS NULL AND END_TIME_ IS NOT NULL, 'DONE_AUTO',
    END_TIME_ IS NOT NULL, 'DONE',
    'TODO'
) AS TASK_STATUS
```

| 狀態 | 條件 | 說明 |
|------|------|------|
| CANCELLED | DELETE_REASON 不為空 | 任務被取消 |
| TODO | 無 ASSIGNEE 且無 END_TIME | 待辦（未指派） |
| DOING | 有 ASSIGNEE 且無 END_TIME | 進行中 |
| DONE_AUTO | 有 ASSIGNEE、無 CLAIM_TIME、有 END_TIME | 自動完成 |
| DONE | 有 END_TIME（其他情況） | 已完成 |

**時長計算**

```sql
-- 閒置時長：任務建立 → 被認領
if(CLAIM_TIME_ IS NOT NULL, 
   dateDiff('second', START_TIME_, CLAIM_TIME_), NULL) AS IDLE_DURATION_SEC,

-- 處理時長：被認領 → 完成
if(CLAIM_TIME_ IS NOT NULL AND END_TIME_ IS NOT NULL, 
   dateDiff('second', CLAIM_TIME_, END_TIME_), NULL) AS WORK_DURATION_SEC,

-- 總時長：任務建立 → 完成
if(END_TIME_ IS NOT NULL, 
   dateDiff('second', START_TIME_, END_TIME_), NULL) AS TOTAL_DURATION_SEC
```

### 6.5 Silver View SQL 範例

```sql
-- V_HI_PROC_TASK_NODE（任務節點 View）
CREATE VIEW silver.V_HI_PROC_TASK_NODE AS
SELECT
    t.ID_ AS TASK_ID,
    t.PROC_INST_ID_ AS PROC_INST_ID,
    t.NAME_ AS TASK_NAME,
    t.ASSIGNEE_ AS ASSIGNEE,
    t.START_TIME_ AS START_TIME,
    t.CLAIM_TIME_ AS CLAIM_TIME,
    t.END_TIME_ AS END_TIME,
    p.BUSINESS_KEY_ AS BUSINESS_KEY,
    
    -- 派生欄位：時長
    if(t.CLAIM_TIME_ IS NOT NULL, dateDiff('second', t.START_TIME_, t.CLAIM_TIME_), NULL) AS IDLE_DURATION_SEC,
    if(t.CLAIM_TIME_ IS NOT NULL AND t.END_TIME_ IS NOT NULL, dateDiff('second', t.CLAIM_TIME_, t.END_TIME_), NULL) AS WORK_DURATION_SEC,
    
    -- 派生欄位：任務狀態
    multiIf(
        t.DELETE_REASON_ IS NOT NULL AND t.DELETE_REASON_ != '', 'CANCELLED',
        t.ASSIGNEE_ IS NULL AND t.END_TIME_ IS NULL, 'TODO',
        t.ASSIGNEE_ IS NOT NULL AND t.END_TIME_ IS NULL, 'DOING',
        t.ASSIGNEE_ IS NOT NULL AND t.CLAIM_TIME_ IS NULL AND t.END_TIME_ IS NOT NULL, 'DONE_AUTO',
        t.END_TIME_ IS NOT NULL, 'DONE',
        'TODO'
    ) AS TASK_STATUS,
    
    -- 流程層變數
    v.PLANT,
    v.FACTORY,
    v.REGION,
    
    -- 流程定義
    pd.NAME_ AS PROC_DEF_NAME,
    
    -- 員工資訊
    e.DeptCodeLname AS DEPT_NAME

FROM bronze.bpm_act_hi_taskinst AS t
LEFT JOIN bronze.bpm_act_hi_procinst AS p ON t.PROC_INST_ID_ = p.PROC_INST_ID_
LEFT JOIN silver.V_PROC_VARIABLES_PIVOTED AS v ON t.PROC_INST_ID_ = v.PROC_INST_ID
LEFT JOIN bronze.bpm_act_re_procdef AS pd ON t.PROC_DEF_ID_ = pd.ID_
LEFT JOIN bronze.common_hr_employee AS e ON t.ASSIGNEE_ = e.EmpCode;
```

### 6.6 Silver RMV 設計

```sql
-- RMV_HI_PROC_TASK_NODE（任務節點 RMV）
CREATE MATERIALIZED VIEW silver.RMV_HI_PROC_TASK_NODE
REFRESH EVERY 1 DAY
ENGINE = ReplacingMergeTree()
ORDER BY TASK_ID
SETTINGS allow_nullable_key = 1
AS
SELECT
    -- 與 View 相同的 SELECT 語句
    ...
FROM bronze.bpm_act_hi_taskinst AS t
LEFT JOIN ...;
```

**RMV 刷新設定**
- 刷新頻率：每天 02:00 UTC（= 10:00 Asia/Taipei）
- 刷新方式：全量刷新（DROP + INSERT）
- 技術要求：ClickHouse 24.3+

**檢查 RMV 刷新狀態**

```sql
SELECT 
    view,
    status,
    last_refresh_time,
    next_refresh_time
FROM system.view_refreshes
WHERE database = 'silver';
```

---

## 7. Gold Layer（Metrics / Aggregates）

### 7.1 設計原則

- **每日快照**：記錄每天的指標值，支援歷史趨勢
- **維度聚合**：按 factory / plant / proc_def_name 聚合
- **分子分母分開存**：比率指標存分子分母，支援重新計算
- **TTL 自動清理**：保留 365 天

### 7.2 Gold 表設計

**DAILY_METRICS_SNAPSHOT（任務 + 流程指標）**

```sql
CREATE TABLE gold.DAILY_METRICS_SNAPSHOT (
    -- 快照時間
    snapshot_date Date COMMENT '快照日期 (Asia/Taipei)',
    snapshot_time DateTime64(3, 'Asia/Taipei') COMMENT '快照時間戳',
    
    -- 維度
    factory LowCardinality(String) COMMENT '工廠',
    plant LowCardinality(String) COMMENT '產品線',
    proc_def_name LowCardinality(String) COMMENT '流程類型',
    
    -- 在途任務指標
    in_progress_task_count UInt64 DEFAULT 0 COMMENT '在途任務數',
    todo_count UInt64 DEFAULT 0 COMMENT '待辦任務數',
    doing_count UInt64 DEFAULT 0 COMMENT '進行中任務數',
    
    -- 自動完成率（分子分母）
    done_auto_count UInt64 DEFAULT 0 COMMENT '自動完成數',
    done_total_count UInt64 DEFAULT 0 COMMENT '已完成總數',
    
    -- 平均處理時長（分子分母）
    total_work_duration_sec UInt64 DEFAULT 0 COMMENT '處理時長總和',
    done_count UInt64 DEFAULT 0 COMMENT '已完成任務數',
    
    -- 流程實例指標
    in_progress_proc_count UInt64 DEFAULT 0 COMMENT '在途流程數',
    completed_proc_count UInt64 DEFAULT 0 COMMENT '已完成流程數',
    
    -- 版本號
    _version UInt64 DEFAULT toUnixTimestamp64Milli(now64(3, 'Asia/Taipei'))
    
) ENGINE = ReplacingMergeTree(_version)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (snapshot_date, factory, plant, proc_def_name)
TTL snapshot_date + INTERVAL 365 DAY DELETE;
```

**DAILY_BIZ_EVENT_SNAPSHOT（業務事件指標）**

```sql
CREATE TABLE gold.DAILY_BIZ_EVENT_SNAPSHOT (
    snapshot_date Date,
    snapshot_time DateTime64(3, 'Asia/Taipei'),
    first_proc_def_name LowCardinality(String),
    in_progress_event_count UInt64 DEFAULT 0,
    completed_event_count UInt64 DEFAULT 0,
    total_event_duration_sec UInt64 DEFAULT 0,
    _version UInt64 DEFAULT toUnixTimestamp64Milli(now64(3, 'Asia/Taipei'))
) ENGINE = ReplacingMergeTree(_version)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (snapshot_date, first_proc_def_name)
TTL snapshot_date + INTERVAL 365 DAY DELETE;
```

### 7.3 Gold 快照 SQL 範例

```sql
-- 建立每日快照
INSERT INTO gold.DAILY_METRICS_SNAPSHOT
WITH 
task_metrics AS (
    SELECT
        COALESCE(FACTORY, '') AS factory,
        COALESCE(PLANT, '') AS plant,
        COALESCE(PROC_DEF_NAME, '') AS proc_def_name,
        countIf(TASK_STATUS IN ('TODO', 'DOING')) AS in_progress_task_count,
        countIf(TASK_STATUS = 'TODO') AS todo_count,
        countIf(TASK_STATUS = 'DOING') AS doing_count,
        countIf(TASK_STATUS = 'DONE_AUTO') AS done_auto_count,
        countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')) AS done_total_count,
        sumIf(toUInt64(WORK_DURATION_SEC), TASK_STATUS = 'DONE') AS total_work_duration_sec,
        countIf(TASK_STATUS = 'DONE') AS done_count
    FROM silver.RMV_HI_PROC_TASK_NODE FINAL
    GROUP BY factory, plant, proc_def_name
),
proc_metrics AS (
    SELECT
        COALESCE(FACTORY, '') AS factory,
        COALESCE(PLANT, '') AS plant,
        COALESCE(PROC_DEF_NAME, '') AS proc_def_name,
        countIf(PROC_STATE = 'DOING') AS in_progress_proc_count,
        countIf(PROC_STATE = 'DONE') AS completed_proc_count
    FROM silver.RMV_HI_PROCINST_NODE FINAL
    GROUP BY factory, plant, proc_def_name
)
SELECT
    toDate('2026-01-13') AS snapshot_date,
    now64(3, 'Asia/Taipei') AS snapshot_time,
    t.factory, t.plant, t.proc_def_name,
    t.in_progress_task_count, t.todo_count, t.doing_count,
    t.done_auto_count, t.done_total_count,
    t.total_work_duration_sec, t.done_count,
    COALESCE(p.in_progress_proc_count, 0),
    COALESCE(p.completed_proc_count, 0),
    toUnixTimestamp64Milli(now64(3, 'Asia/Taipei'))
FROM task_metrics t
LEFT JOIN proc_metrics p 
    ON t.factory = p.factory 
    AND t.plant = p.plant 
    AND t.proc_def_name = p.proc_def_name;
```

### 7.4 Gold 指標清單

| 指標 | 定義 | 聚合方式 |
|------|------|----------|
| 在途任務數 | TODO + DOING 狀態的任務數 | 可 SUM |
| 自動完成率 | DONE_AUTO / (DONE + DONE_AUTO) | 需重算 |
| 平均處理時長 | total_work_duration / done_count | 需重算 |
| 在途流程數 | DOING 狀態的流程數 | 可 SUM |
| 已完成流程數 | DONE 狀態的流程數 | 可 SUM |
| 在途業務事件數 | IS_IN_PROGRESS = 1 的事件數 | 可 SUM |
| 平均業務事件歷時 | total_duration / completed_count | 需重算 |

---

## 8. Orchestration

### 8.1 目前狀態

本專案目前**尚未實作自動化排程**，所有同步和快照都是手動執行。

**原因**：
- MVP 階段，優先驗證資料正確性
- 排程需求尚未明確（頻率、時間點）
- 避免過早引入複雜度

### 8.2 建議的 DAG 結構（未來實作）

```
┌─────────────────────────────────────────────────────────────────┐
│                        Daily DAG                                │
│                                                                 │
│  09:00 ─► bronze_sync ─► wait_rmv_refresh ─► gold_snapshot     │
│              │                  │                  │            │
│              ▼                  ▼                  ▼            │
│         sync_incremental   (自動 10:00)    create_gold_snapshot │
│                                                                 │
│  ─► data_quality_check ─► alert_on_failure                     │
│              │                  │                               │
│              ▼                  ▼                               │
│         row_count_check    send_slack_alert                    │
└─────────────────────────────────────────────────────────────────┘
```

### 8.3 手動執行流程

```bash
# Step 1: Bronze 同步
python sync/sync_incremental.py all

# Step 2: 等待 RMV 刷新（或手動觸發）
# RMV 會在 02:00 UTC (10:00 TPE) 自動刷新
# 或手動刷新：
python -c "
import clickhouse_connect
client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121)
client.command('SYSTEM REFRESH VIEW silver.RMV_HI_PROC_TASK_NODE')
"

# Step 3: Gold 快照
python scripts/create_gold_snapshot.py

# Step 4: 驗證
python scripts/query_metrics_rmv.py
```

### 8.4 重跑與失敗處理

**Bronze 同步失敗**
- 直接重新執行即可
- 增量同步：從上次 watermark 繼續
- 全量同步：DROP + CREATE 天然冪等

**RMV 刷新失敗**
- 檢查 system.view_refreshes 狀態
- 手動觸發刷新：`SYSTEM REFRESH VIEW silver.RMV_*`

**Gold 快照失敗**
- 直接重新執行即可
- ReplacingMergeTree 會自動去重

---

## 9. Data Quality & Audit

### 9.1 對帳策略

**Row Count 比對**

```sql
-- MSSQL vs ClickHouse 筆數比對
SELECT 
    'MSSQL' as source,
    count(*) as cnt
FROM jdbc('mssql_master', 'SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST')
UNION ALL
SELECT 
    'ClickHouse' as source,
    count(*) as cnt
FROM bronze.bpm_act_hi_taskinst FINAL;
```

**View vs RMV 一致性**

```sql
-- 比對 View 和 RMV 的指標值
SELECT
    'View' as source,
    countIf(TASK_STATUS IN ('TODO', 'DOING')) as in_progress
FROM silver.V_HI_PROC_TASK_NODE
UNION ALL
SELECT
    'RMV' as source,
    countIf(TASK_STATUS IN ('TODO', 'DOING')) as in_progress
FROM silver.RMV_HI_PROC_TASK_NODE FINAL;
```

### 9.2 稽核 SQL 範例

```sql
-- 檢查 Watermark 狀態
SELECT 
    table_name,
    last_sync_time,
    sync_time,
    row_count,
    dateDiff('hour', last_sync_time, now()) as hours_since_last_sync
FROM bronze._sync_watermark FINAL
ORDER BY table_name;

-- 檢查 RMV 刷新狀態
SELECT 
    view,
    status,
    last_refresh_time,
    next_refresh_time,
    dateDiff('hour', last_refresh_time, now()) as hours_since_refresh
FROM system.view_refreshes
WHERE database = 'silver';

-- 檢查 Gold 快照連續性
SELECT 
    snapshot_date,
    count(*) as dimension_count,
    sum(in_progress_task_count) as total_in_progress
FROM gold.DAILY_METRICS_SNAPSHOT FINAL
GROUP BY snapshot_date
ORDER BY snapshot_date DESC
LIMIT 7;
```

### 9.3 驗證腳本

```bash
# 環境檢查
python scripts/check_my_env.py

# RMV 刷新狀態
python scripts/check_rmv_status.py

# View vs RMV 一致性
python scripts/compare_view_rmv.py

# 資料準確性
python scripts/compare_data_accuracy.py
```

---

## 10. Performance & Cost Considerations

### 10.1 Partition / Order Key 設計

**Bronze 表**

| 表 | PARTITION BY | ORDER BY | 原因 |
|-----|--------------|----------|------|
| bpm_act_hi_procinst | toYYYYMM(START_TIME_) | (PROC_DEF_ID_, START_TIME_, ID_) | 按月分區，常用查詢條件 |
| bpm_act_hi_taskinst | toYYYYMM(START_TIME_) | (PROC_INST_ID_, START_TIME_, ID_) | 按流程實例查詢 |
| bpm_act_hi_varinst | toYYYYMM(CREATE_TIME_) | (PROC_INST_ID_, NAME_, ID_) | 按流程實例和變數名查詢 |
| 小表 | 無 | tuple() | 資料量小，無需分區 |

**Silver RMV**

| 表 | ORDER BY | 原因 |
|-----|----------|------|
| RMV_HI_PROC_TASK_NODE | TASK_ID | 主鍵查詢 |
| RMV_HI_PROCINST_NODE | PROC_INST_ID | 主鍵查詢 |
| RMV_HI_BIZ_EVENT_INFO | BIZ_EVENT_KEY | 主鍵查詢 |

**Gold 表**

| 表 | PARTITION BY | ORDER BY | 原因 |
|-----|--------------|----------|------|
| DAILY_METRICS_SNAPSHOT | toYYYYMM(snapshot_date) | (snapshot_date, factory, plant, proc_def_name) | 按日期和維度查詢 |
| DAILY_BIZ_EVENT_SNAPSHOT | toYYYYMM(snapshot_date) | (snapshot_date, first_proc_def_name) | 按日期和流程類型查詢 |

### 10.2 TTL / 壓縮

**TTL 設定**
- Gold 表：365 天自動刪除
- Bronze 表：目前無 TTL（保留全部歷史）

```sql
-- Gold 表 TTL
TTL snapshot_date + INTERVAL 365 DAY DELETE
```

**壓縮**
- 使用 ClickHouse 預設壓縮（LZ4）
- 未額外設定 CODEC

### 10.3 常見效能陷阱

| 陷阱 | 說明 | 解決方案 |
|------|------|----------|
| 忘記 FINAL | ReplacingMergeTree 查詢未去重 | 查詢時加 FINAL 或定期 OPTIMIZE |
| View 效能差 | 每次查詢即時計算 | 使用 RMV 替代 |
| JDBC Bridge 超時 | 大表查詢超時 | 分批查詢或增加超時設定 |
| 跨時區問題 | 時間欄位時區不一致 | 統一使用 Asia/Taipei |

### 10.4 效能數據（實測）

| 操作 | 耗時 | 說明 |
|------|------|------|
| 全量同步 (16 表) | ~68 秒 | 2.1M 筆 |
| 增量同步 (5 表) | ~10 秒 | 視增量資料量 |
| RMV 刷新 | ~30 秒 | 4 張 RMV |
| Gold 快照 | ~5 秒 | 2 張表 |
| View 查詢 | 95-147 ms | 單一指標 |
| RMV 查詢 | 11-15 ms | 單一指標 |

---

## 11. Observability

### 11.1 必要監控指標

| 指標 | 說明 | 告警條件 |
|------|------|----------|
| 同步延遲 | 上次同步到現在的時間 | > 24 小時 |
| RMV 刷新狀態 | 刷新是否成功 | status != 'Scheduled' |
| 資料筆數差異 | MSSQL vs ClickHouse | 差異 > 1% |
| Gold 快照連續性 | 是否有缺漏日期 | 缺漏 > 1 天 |

### 11.2 監控 SQL

```sql
-- 同步延遲監控
SELECT 
    table_name,
    dateDiff('hour', last_sync_time, now()) as hours_since_sync,
    if(dateDiff('hour', last_sync_time, now()) > 24, 'ALERT', 'OK') as status
FROM bronze._sync_watermark FINAL;

-- RMV 刷新監控
SELECT 
    view,
    status,
    if(status != 'Scheduled', 'ALERT', 'OK') as alert_status
FROM system.view_refreshes
WHERE database = 'silver';
```

### 11.3 日誌與追蹤

**同步日誌**
- 位置：`logs/sync_incremental_*.txt`
- 內容：每次同步的表、筆數、耗時、狀態

**範例日誌**

```
====================================================================================================
同步結果 Summary - 2026-01-13 10:00:00
====================================================================================================
步驟                                          類型         耗時(秒)   筆數         狀態
----------------------------------------------------------------------------------------------------
bronze.bpm_act_hi_procinst                    incremental  2.34       150          success
bronze.bpm_act_hi_taskinst                    incremental  3.21       320          success
bronze.common_hr_employee                     full         1.05       5234         success
----------------------------------------------------------------------------------------------------
總耗時: 10.23 秒
總筆數: 5,704
====================================================================================================
```

---

## 12. Cube.js Semantic Layer

### 12.1 架構

```
Silver RMV ──► Cube.js ──► REST API (4002) / Playground (4003)
Gold Tables ──┘
```

### 12.2 Cube 建立在 Silver 或 Gold 的理由

| 來源 | Cube | 用途 |
|------|------|------|
| Silver RMV | ProcTaskNode, ProcInstNode, BizEventInfo | 即時指標查詢 |
| Gold Tables | DailyMetricsSnapshot, DailyBizEventSnapshot | 歷史趨勢查詢 |

**選擇 RMV 而非 View 的原因**：
- 效能：RMV 查詢快 4-10 倍
- 穩定：預計算結果，不受 Bronze 資料變動影響
- 資料延遲可接受：報表場景不需要秒級即時

### 12.3 Cube Schema 範例

**ProcTaskNode（任務節點）**

```javascript
cube(`ProcTaskNode`, {
  sql: `
    SELECT 
      TASK_ID, PROC_INST_ID, PROC_DEF_NAME, BUSINESS_KEY,
      TASK_NAME, TASK_STATUS, ASSIGNEE, DEPT_NAME,
      FACTORY, PLANT, LINE_NAME, REGION,
      START_TIME, END_TIME, CLAIM_TIME,
      IDLE_DURATION_SEC, WORK_DURATION_SEC, TOTAL_DURATION_SEC
    FROM silver.RMV_HI_PROC_TASK_NODE
  `,

  title: '任務節點',
  description: '流程任務的詳細資訊',

  dimensions: {
    taskId: { sql: `TASK_ID`, type: `string`, primaryKey: true },
    procDefName: { sql: `PROC_DEF_NAME`, type: `string` },
    taskStatus: { sql: `TASK_STATUS`, type: `string` },
    factory: { sql: `FACTORY`, type: `string` },
    plant: { sql: `PLANT`, type: `string` },
    assignee: { sql: `ASSIGNEE`, type: `string` },
    deptName: { sql: `DEPT_NAME`, type: `string` },
    startTime: { sql: `START_TIME`, type: `time` },
  },

  measures: {
    // Gold 指標
    inProgressTaskCount: {
      sql: `TASK_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.TASK_STATUS IN ('TODO', 'DOING')` }],
      title: '在途任務數',
    },
    
    autoCompleteRate: {
      sql: `${doneAutoForRate} * 100.0 / NULLIF(${doneTotalForRate}, 0)`,
      type: `number`,
      title: '自動完成率 (%)',
    },
    
    avgWorkDuration: {
      sql: `WORK_DURATION_SEC`,
      type: `avg`,
      filters: [{ sql: `${CUBE}.TASK_STATUS = 'DONE'` }],
      title: '平均處理時長 (秒)',
    },
    
    // 輔助指標（分子分母）
    doneAutoForRate: {
      sql: `TASK_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.TASK_STATUS = 'DONE_AUTO'` }],
    },
    doneTotalForRate: {
      sql: `TASK_ID`,
      type: `count`,
      filters: [{ sql: `${CUBE}.TASK_STATUS IN ('DONE', 'DONE_AUTO')` }],
    },
  },
});
```

**DailyMetricsSnapshot（歷史趨勢）**

```javascript
cube(`DailyMetricsSnapshot`, {
  sql: `SELECT * FROM gold.DAILY_METRICS_SNAPSHOT FINAL`,
  
  title: '每日指標快照',
  description: 'Gold 層每日快照，支援歷史趨勢查詢',

  dimensions: {
    snapshotDate: { type: `time`, sql: `snapshot_date` },
    factory: { type: `string`, sql: `factory` },
    plant: { type: `string`, sql: `plant` },
    procDefName: { type: `string`, sql: `proc_def_name` },
  },

  measures: {
    inProgressTaskCount: {
      type: `sum`,
      sql: `in_progress_task_count`,
      title: '在途任務數',
    },
    
    autoCompleteRate: {
      type: `number`,
      sql: `CASE WHEN ${doneTotalCount} > 0 
            THEN ${doneAutoCount} * 100.0 / ${doneTotalCount} 
            ELSE 0 END`,
      title: '自動完成率 (%)',
    },
    
    doneAutoCount: { type: `sum`, sql: `done_auto_count` },
    doneTotalCount: { type: `sum`, sql: `done_total_count` },
    
    inProgressProcCount: {
      type: `sum`,
      sql: `in_progress_proc_count`,
      title: '在途流程數',
    },
  },
});
```

### 12.4 Cube.js View（對外 API）

```javascript
view(`HistoricalTrends`, {
  title: '歷史趨勢',
  description: '查詢歷史指標趨勢',

  cubes: [
    {
      join_path: DailyMetricsSnapshot,
      includes: [
        { name: 'snapshotDate', alias: 'snapshotDate' },
        { name: 'factory', alias: 'factory' },
        { name: 'plant', alias: 'plant' },
        { name: 'inProgressTaskCount', alias: 'inProgressTaskCount' },
        { name: 'autoCompleteRate', alias: 'autoCompleteRate' },
        { name: 'inProgressProcCount', alias: 'inProgressProcCount' },
      ],
    },
  ],
});
```

### 12.5 查詢範例

**REST API 查詢**

```bash
# 在途任務數（依廠區）
curl -X POST http://localhost:4002/cubejs-api/v1/load \
  -H "Content-Type: application/json" \
  -d '{
    "measures": ["ProcTaskNode.inProgressTaskCount"],
    "dimensions": ["ProcTaskNode.factory"]
  }'

# 歷史趨勢（最近 30 天）
curl -X POST http://localhost:4002/cubejs-api/v1/load \
  -H "Content-Type: application/json" \
  -d '{
    "measures": ["HistoricalTrends.inProgressTaskCount"],
    "timeDimensions": [{
      "dimension": "HistoricalTrends.snapshotDate",
      "granularity": "day",
      "dateRange": "last 30 days"
    }]
  }'
```

**Playground 查詢**

訪問 http://localhost:4003 使用圖形化介面查詢。

---

## 13. Deployment & Config

### 13.1 環境變數與設定檔結構

```
project/
├── docker/
│   ├── docker-compose.yml              # ClickHouse + JDBC Bridge (已註解)
│   └── jdbc-bridge/
│       └── config/
│           └── datasources/
│               └── mssql_master.json   # MSSQL 連線設定
├── cube/
│   ├── docker-compose.yml              # Cube.js 部署
│   ├── .env.example                    # 環境變數範例
│   └── model/
│       └── cubes/                      # Cube 定義
├── sync/
│   ├── sync_to_clickhouse.py           # 全量同步
│   └── sync_incremental.py             # 增量同步
└── scripts/
    └── create_gold_snapshot.py         # Gold 快照
```

### 13.2 連線設定

**ClickHouse**

```python
# Python 連線設定
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
}
```

**Cube.js**

```yaml
# cube/docker-compose.yml
environment:
  - CUBEJS_DB_TYPE=clickhouse
  - CUBEJS_DB_HOST=REDACTED_IP
  - CUBEJS_DB_PORT=8121
  - CUBEJS_DB_USER=default
  - CUBEJS_DB_PASS=default
  - CUBEJS_DB_NAME=silver
  - CUBEJS_DEV_MODE=true
  - CUBEJS_API_SECRET=REDACTED_SECRET
```

### 13.3 dev / stg / prd 差異化方式

**目前狀態**：本專案目前只有單一環境（開發/測試用）

**未來建議**：

| 環境 | ClickHouse Host | Cube.js Port | 說明 |
|------|-----------------|--------------|------|
| dev | localhost:8123 | 4002/4003 | 本機開發 |
| stg | REDACTED_IP:8121 | 4002/4003 | 測試環境（目前） |
| prd | TBD | TBD | 生產環境（未建立） |

**環境切換方式**：
- 使用環境變數或設定檔
- 目前硬編碼在腳本中（待改善）

---

## 14. Acceptance Checklist

### 14.1 可跑通

- [x] MSSQL → ClickHouse 同步可執行
- [x] Bronze 16 張表建立完成
- [x] Silver View 4 張建立完成
- [x] Silver RMV 4 張建立完成
- [x] Gold 2 張表建立完成
- [x] Cube.js 可啟動並查詢

### 14.2 可重跑

- [x] Bronze 增量同步可重跑（Watermark + ReplacingMergeTree）
- [x] Bronze 全量同步可重跑（DROP + CREATE）
- [x] Gold 快照可重跑（ReplacingMergeTree 去重）

### 14.3 可回補

- [x] Bronze 可回補（調整 Watermark 或重建表）
- [x] Gold 可回補（指定日期執行快照）

### 14.4 可對帳

- [x] MSSQL vs ClickHouse 筆數比對
- [x] View vs RMV 一致性驗證
- [x] 指標邏輯等價性驗證

### 14.5 Cube.js 可查詢

- [x] REST API 可查詢（localhost:4002）
- [x] Playground 可使用（localhost:4003）
- [x] 7 個 Gold 指標可查詢

---

## 15. FAQ / Troubleshooting

### Q1: JDBC Bridge 連線失敗

**症狀**：`Connection refused` 或 `Timeout`

**解決方案**：
1. 確認 JDBC Bridge 服務運行中
2. 確認 MSSQL 可從 ClickHouse 主機連線
3. 使用 IP 而非 hostname
4. 使用 JDBC Driver 7.4.1（非 12.x）

### Q2: RMV 刷新失敗

**症狀**：`system.view_refreshes` 顯示 `Error`

**解決方案**：
1. 檢查 Bronze 表是否存在
2. 檢查 ClickHouse 版本 >= 24.3
3. 手動刷新：`SYSTEM REFRESH VIEW silver.RMV_*`

### Q3: 資料筆數不一致

**症狀**：MSSQL 和 ClickHouse 筆數不同

**解決方案**：
1. 確認查詢時使用 FINAL
2. 執行 `OPTIMIZE TABLE ... FINAL` 強制合併
3. 檢查 Watermark 是否正確

### Q4: Cube.js 查詢慢

**症狀**：查詢超過 10 秒

**解決方案**：
1. 確認 Cube.js 讀取 RMV 而非 View
2. 檢查 ClickHouse 資源使用
3. 考慮啟用 Pre-aggregations

### Q5: Gold 快照缺漏

**症狀**：某些日期沒有快照資料

**解決方案**：
1. 手動執行指定日期的快照
2. `python scripts/create_gold_snapshot.py --date 2026-01-12`

### Q6: 時區問題

**症狀**：時間欄位顯示不正確

**解決方案**：
1. Gold 表使用 `DateTime64(3, 'Asia/Taipei')`
2. 查詢時注意時區轉換
3. MSSQL 時間假設為 UTC+8

---

## 附錄 A: 檔案清單

| 檔案 | 用途 |
|------|------|
| `sync/sync_incremental.py` | Bronze 增量+全量同步 |
| `sync/sync_to_clickhouse.py` | Bronze 全量同步（舊版） |
| `scripts/create_gold_snapshot.py` | Gold 快照 |
| `scripts/check_rmv_status.py` | RMV 狀態檢查 |
| `scripts/query_metrics_rmv.py` | 指標查詢 |
| `sql/02_create_bpm_tables.sql` | Bronze DDL |
| `sql/05_create_silver_views.sql` | Silver View DDL |
| `sql/06_create_silver_rmv.sql` | Silver RMV DDL |
| `sql/07_create_gold_snapshot.sql` | Gold DDL |
| `cube/model/cubes/*.js` | Cube.js Model |

## 附錄 B: 實作狀態總覽

| 元件 | 狀態 | 說明 |
|------|------|------|
| Bronze 同步 | ✅ 已完成 | 16 張表，增量+全量混合 |
| Silver View | ✅ 已完成 | 4 張 View |
| Silver RMV | ✅ 已完成 | 4 張 RMV，每日自動刷新 |
| Gold 快照 | ✅ 已完成 | 2 張表，手動執行 |
| Cube.js | ✅ 已完成 | 5 Cubes + 2 Views |
| 自動化排程 | ⏸️ 尚未實作 | 需外部工具 |
| 監控告警 | ⏸️ 尚未實作 | 有 SQL，無自動化 |
| 多環境部署 | ⏸️ 尚未實作 | 目前單一環境 |

---

*文件結束*
