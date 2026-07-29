# ClickHouse ODBC 資料同步配置手冊

**文件編號**: 01-ARCH-002  
**版本**: 3.0  
**最後更新**: 2026-04-14  
**狀態**: 正式發布 (Released)  
**維護者**: AIT / Data Engineering

---

## 目錄 (Table of Contents)

1. [架構概述](#1-架構概述)
2. [ODBC DSN 配置](#2-odbc-dsn-配置)
3. [ClickHouse 原生 ODBC 引擎](#3-clickhouse-原生-odbc-引擎)
4. [同步工具 - sync_unified_odbc.py](#4-同步工具---sync_unified_odbcpy)
5. [同步策略](#5-同步策略)
6. [水位線與狀態追蹤](#6-水位線與狀態追蹤)
7. [容錯機制](#7-容錯機制)
8. [運維指令參考](#8-運維指令參考)
9. [相關文件](#9-相關文件)

---

## 1. 架構概述

本文件說明如何配置 ClickHouse 與 MSSQL 之間的原生 ODBC 同步機制。此機制完全移除舊有的 JDBC Bridge 依賴，直接利用 ClickHouse 內建的 `ODBC` 表引擎搭配 **Microsoft ODBC Driver 18 for SQL Server**，在資料庫引擎間進行高速 C++ 底層直傳。

**核心優勢**：資料傳輸路徑不經過 Python 記憶體，由 ClickHouse 的 C++ 底層直接向 MSSQL 拉取，實測吞吐量可達 **90,000+ 筆/秒**。

```
MSSQL (APP_SRV_BPM / APP_SRV_COMMON)
        │
        │  Microsoft ODBC Driver 18 for SQL Server
        │  (系統層 DSN: MSSQL_DSN)
        ▼
ClickHouse ODBC Table Engine (C++ 底層直傳)
        │
        │  Python sync_unified_odbc.py (調度 / 切窗 / 容錯)
        ▼
bronze.* (18 張原始資料表)
```

---

## 2. ODBC DSN 配置

系統預期於作業系統層級預先配置一個名為 `MSSQL_DSN` 的資料來源名稱 (DSN)。

### 2.1 DSN 基本參數

| 參數            | 設定值                                  | 說明                                            |
| :-------------- | :-------------------------------------- | :---------------------------------------------- |
| **DSN 名稱**    | `MSSQL_DSN`                             | 須與 `sync_tables.yaml` 中連線字串一致          |
| **驅動程式**    | `ODBC Driver 18 for SQL Server`         | 注意：舊版 Driver 17 已不適用，請使用 Driver 18  |
| **Server**      | MSSQL 伺服器 IP 或主機名稱              | 依環境而定                                       |
| **TrustServerCertificate** | `yes`                      | 避免自簽憑證導致連線失敗                         |
| **MARS_Connection** | `yes`                               | 支援多重活動結果集，避免大量批次時的 TCP 阻塞    |

### 2.2 DSN 配置範例 (odbc.ini)

```ini
[MSSQL_DSN]
Driver    = ODBC Driver 18 for SQL Server
Server    = <MSSQL_SERVER_IP>
TrustServerCertificate = yes
MARS_Connection = yes
```

> **重要提示**：連線的帳號密碼不應寫入 `odbc.ini`，應透過 `sync_unified_odbc.py` 在執行期間動態從環境變數注入。憑證配置請參閱 `infra/clickhouse/odbc/.env`。

---

## 3. ClickHouse 原生 ODBC 引擎

### 3.1 Explicit DDL Bypass 模式

**問題背景**：Microsoft ODBC Driver 18 在連線 MSSQL 時，會自動執行動態 Schema 探測 (Metadata Discovery)。當來源表含有 `varchar(max)` 或 `xml` 型別欄位時，此行為會導致 ODBC Bridge 陷入死鎖 (Deadlock)，長達數分鐘無回應。

**解決方案**：`sync_unified_odbc.py` 採用「顯式 DDL 代理表 (Explicit DDL Bypass)」策略，在 ClickHouse 中動態建立帶有**明確欄位型別定義**的暫時性 ODBC 引擎表，完全繞過 Driver 的自動探測行為。

### 3.2 臨時代理表 DDL 範例

```sql
-- sync_unified_odbc.py 為每次同步動態建立並在完成後自動銷毀的暫時表
CREATE TABLE odbc_temp_taskinst (
    ID_              String,
    REV_             Int32,
    PROC_DEF_ID_     String,
    TASK_DEF_KEY_    String,
    PROC_INST_ID_    String,
    EXECUTION_ID_    String,
    NAME_            String,
    ASSIGNEE_        String,
    START_TIME_      DateTime,
    CLAIM_TIME_      DateTime,
    END_TIME_        DateTime,
    DURATION_        Int64,
    DELETE_REASON_   String,
    LAST_UPDATED_TIME_ DateTime
) ENGINE = ODBC(
    'DSN=MSSQL_DSN;Database=APP_SRV_BPM;Uid=<user>;Pwd=<pass>',
    'dbo',
    'ACT_HI_TASKINST_0108'
);
```

欄位型別定義的來源為 `scripts/etl/config/sync_tables.yaml` 中的 `engine_ddl` 欄位，由維護人員依來源表 Schema 手動維護。

---

## 4. 同步工具 - sync_unified_odbc.py

`sync_unified_odbc.py` 是 MSSQL → ClickHouse Bronze 層的核心抽取引擎，負責調度所有 18 張來源表的同步作業。

### 4.1 設定檔依賴

同步工具的行為完全由 `scripts/etl/config/sync_tables.yaml` 驅動：

```
sync_tables.yaml
├── <table_key>                     # 表格識別鍵 (如 taskinst、varinst)
│   ├── source                      # MSSQL 來源表 (含 DB 名稱與 schema)
│   ├── target                      # ClickHouse 目標表 (bronze.<name>)
│   ├── strategy                    # 同步策略: "batch" 或 "full"
│   ├── time_col                    # 增量時間欄位 (batch 策略必填)
│   ├── step_days                   # 批次視窗大小 (預設 10 天)
│   ├── engine_ddl                  # 顯式欄位型別定義 (Bypass 用)
│   └── columns                     # SELECT 欄位清單
```

**目前配置的 18 張表** (`sync_tables.yaml`)：

| 識別鍵                 | 來源 DB               | 目標表                                  | 策略    |
| :--------------------- | :-------------------- | :-------------------------------------- | :------ |
| `hr_employee`          | APP_SRV_COMMON        | `bronze.common_hr_employee`             | full    |
| `emp_node_role`        | APP_SRV_COMMON        | `bronze.common_emp_node_role_mapping`   | full    |
| `emp_org_info`         | APP_SRV_COMMON        | `bronze.common_emp_org_info_mapping`    | full    |
| `emp_user_group`       | APP_SRV_COMMON        | `bronze.common_emp_user_group_mapping`  | full    |
| `user_group`           | APP_SRV_COMMON        | `bronze.common_user_group`              | full    |
| `process_role_user`    | APP_SRV_COMMON        | `bronze.common_process_role_user_mapping` | full  |
| `mdm_line_desc`        | APP_SRV_COMMON        | `bronze.common_mdm_line_desc_master`    | full    |
| `mdm_prod_area`        | APP_SRV_COMMON        | `bronze.common_mdm_prod_area_master`    | full    |
| `mdm_factory_area`     | APP_SRV_COMMON        | `bronze.common_mdm_factory_area_master` | full    |
| `mdm_mfg_site`         | APP_SRV_COMMON        | `bronze.common_mdm_mfg_site_master`     | full    |
| `mdm_mfg_plant`        | APP_SRV_COMMON        | `bronze.common_mdm_mfg_plant_master`    | full    |
| `dmp_func_config`      | APP_SRV_COMMON        | `bronze.common_dmp_function_config`     | full    |
| `dmp_func_client_mapping` | APP_SRV_COMMON     | `bronze.common_dmp_function_client_mapping` | full |
| `procdef`              | APP_SRV_BPM           | `bronze.bpm_act_re_procdef`             | full    |
| `taskinst`             | APP_SRV_BPM           | `bronze.bpm_act_hi_taskinst`            | batch   |
| `varinst`              | APP_SRV_BPM           | `bronze.bpm_act_hi_varinst`             | batch   |
| `procinst`             | APP_SRV_BPM           | `bronze.bpm_act_hi_procinst`            | batch   |
| `identitylink`         | APP_SRV_BPM           | `bronze.bpm_act_hi_identitylink`        | batch   |

---

## 5. 同步策略

### 5.1 批次增量同步 (strategy: batch)

適用對象：高異動量的流程引擎記錄表（`TaskInst`、`VarInst`、`ProcInst`、`IdentityLink`）。

```
執行流程:
  1. 讀取 bronze._sync_watermark 取得上次同步的 last_sync_time
  2. 以 step_days (預設 10 天) 切割時間視窗
  3. 對每個視窗:
       a. 建立 ODBC 暫時代理表
       b. 執行 INSERT INTO bronze.<target>
              SELECT ... FROM odbc_temp_<key>
              WHERE <time_col> >= '<window_start>'
                AND <time_col> <  '<window_end>'
       c. 成功後更新 _sync_watermark
       d. 銷毀暫時代理表
  4. 重複直到追上當前時間
```

### 5.2 全量同步 (strategy: full)

適用對象：異動頻率低或需要 1:1 對齊的維度主檔（HR 員工、MDM 五階製造維度等）。

```
執行流程:
  1. TRUNCATE bronze.<target>      -- 清空目標表
  2. 建立 ODBC 暫時代理表
  3. INSERT INTO bronze.<target>
         SELECT <columns>
         FROM odbc_temp_<key>      -- 全量寫入
  4. 更新 _sync_watermark
  5. 銷毀暫時代理表
```

---

## 6. 水位線與狀態追蹤

所有同步進度均記錄於 `bronze._sync_watermark` 表中，格式為 `ReplacingMergeTree`，主鍵為 `table_name`。

### 6.1 水位線表結構

| 欄位             | 型別       | 說明                         |
| :--------------- | :--------- | :--------------------------- |
| `table_name`     | String     | Bronze 目標表名稱             |
| `last_sync_time` | DateTime   | 來源端最後同步到的時間點      |
| `sync_time`      | DateTime   | 本次同步完成的時間            |
| `row_count`      | Int64      | 累計同步筆數                  |
| `_sync_version`  | UInt64     | ReplacingMergeTree 版本欄位   |

### 6.2 查詢水位線狀態

```sql
-- 查詢所有表的同步進度
SELECT table_name, last_sync_time, sync_time, row_count
FROM bronze._sync_watermark
FINAL
ORDER BY table_name;
```

### 6.3 查詢 ETL Checkpoint（計算進度）

```sql
-- 查詢最近 20 筆計算階段完成紀錄
SELECT
    phase, window_start, window_end, status,
    round(duration_ms / 1000, 2) AS duration_sec,
    formatReadableSize(result_bytes) AS size,
    result_rows AS rows,
    update_time
FROM ops_metrics.etl_checkpoint
FINAL
ORDER BY update_time DESC
LIMIT 20;
```

---

## 7. 容錯機制

### 7.1 自適應分批 (Adaptive Batching)

當單一批次同步失敗（連線逾時、網路中斷）時，腳本自動將當前時間視窗切分為兩半後遞迴重試。最小批次粒度為 **30 分鐘**，防止無限切分。

```
批次視窗失敗示例:
  原視窗: 2025-03-01 ~ 2025-03-11 (10 天)
  失敗後自動切分為:
    ├── 2025-03-01 ~ 2025-03-06 (5 天) → 重試
    └── 2025-03-06 ~ 2025-03-11 (5 天) → 重試
```

### 7.2 Session 自動重建

連線逾時或被 MSSQL 重置時，腳本自動關閉當前 Client 並重新建立連線，無需人工介入。

### 7.3 中斷續傳

腳本每次執行均從 `_sync_watermark` 讀取上次成功的 `last_sync_time`，自動從斷點位置繼續，不會重複抓取已完成的資料。

---

## 8. 運維指令參考

```bash
# 同步所有 18 張表 (自動從 Watermark 斷點續傳)
python scripts/etl/sync_unified_odbc.py

# 同步指定表 (使用 sync_tables.yaml 的識別鍵)
python scripts/etl/sync_unified_odbc.py --table taskinst
python scripts/etl/sync_unified_odbc.py --table hr_employee
python scripts/etl/sync_unified_odbc.py --table varinst

# 同步指定表並覆蓋起始日期 (強制從該日期重新抓取)
python scripts/etl/sync_unified_odbc.py --table taskinst --start 2025-01-01

# 預覽模式 (列印計劃但不實際執行)
python scripts/etl/sync_unified_odbc.py --dry-run

# 查詢 Watermark 現有進度 (建議搭配 execute_etl.py --status)
python scripts/etl/execute_etl.py --status
```

> **注意**：`--table` 參數的值須為 `sync_tables.yaml` 中定義的識別鍵（如 `taskinst`、`varinst`），而非 ClickHouse 的目標表名稱。

---

## 9. 相關文件

| 文件                             | 路徑                                                                             |
| :------------------------------- | :------------------------------------------------------------------------------- |
| 系統架構總覽                     | `docs/01_architecture/Architecture_Overview.md`                               |
| 同步策略與 Watermark 操作說明   | `docs/02_deployment/Deployment_Guide.md`              |
| 同步表設定檔                     | `scripts/etl/config/sync_tables.yaml`                                            |
| ODBC 驅動容器設定                | `infra/clickhouse/odbc/`                                                         |
| 完整技術設計文件                 | `docs/DMP_Flowable_Technical_Documentation.md` → §6.2                           |

---

**文件負責人**: AIT / Data Engineering  
**審核狀態**: 已對照 `sync_unified_odbc.py`、`sync_tables.yaml`、`infra/clickhouse/odbc/` 驗證完成
