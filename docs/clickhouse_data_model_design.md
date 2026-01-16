# ClickHouse 資料模型設計文件

## 1. MSSQL Reference SQL 語意拆解

### 1.1 資料來源與欄位分類

| 分類 | 來源表 | JOIN 條件 | 欄位 |
|------|--------|-----------|------|
| **流程主表** | `ACT_HI_PROCINST` | 主表 | `PROC_INST_ID_`, `PROC_DEF_ID_`, `DELETE_REASON_` |
| **流程定義** | `ACT_RE_PROCDEF` | `hi.PROC_DEF_ID_ = pd.ID_` | `KEY_`, `NAME_` |
| **任務主表** | `ACT_HI_TASKINST` | `hi.PROC_INST_ID_ = hti.PROC_INST_ID_` | `ID_`, `TASK_DEF_KEY_`, `NAME_`, `ASSIGNEE_`, `START_TIME_`, `CLAIM_TIME_`, `END_TIME_` |
| **流程層級變數** | `ACT_HI_VARINST` | `hi.PROC_INST_ID_ = var.PROC_INST_ID_` | `plant`, `factory`, `lineName`, `moNumber`, `region`, 等 |
| **Task 層級變數** | `ACT_HI_VARINST` | `hti.ID_ = var.TASK_ID_` | `autoComplete` (用於 taskBypass) |
| **人員維度** | `HR_Employee` | `hti.ASSIGNEE_ = he.EmpCode` | `ADAccount`, `EmpName` |

### 1.2 關鍵計算邏輯

**taskStatus 計算**:
```sql
CASE
    WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
    WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
    ELSE 'TODO'
END
```

**taskBypass 計算**:
```sql
-- 從 Task 層級變數 autoComplete 取值
CASE WHEN var_bypass.LONG_ = 1 THEN 'Y' ELSE 'N' END
-- 注意：JOIN 條件是 hti.ID_ = var_bypass.TASK_ID_（不是 PROC_INST_ID_）
```

### 1.3 變數層級區分

| 變數名稱 | 層級 | JOIN Key | 說明 |
|----------|------|----------|------|
| `plant` | 流程層級 | `PROC_INST_ID_` | 製造廠區 |
| `factory` | 流程層級 | `PROC_INST_ID_` | 製造產品廠 |
| `lineName` | 流程層級 | `PROC_INST_ID_` | 線體 |
| `moNumber` | 流程層級 | `PROC_INST_ID_` | 工單編號 |
| `region` | 流程層級 | `PROC_INST_ID_` | 地區 |
| `autoComplete` | **Task 層級** | `TASK_ID_` | 是否自動完成（bypass） |

---

## 2. ClickHouse Bronze/Silver/Gold 表設計

### 2.1 Bronze 層（已存在）

Bronze 層已同步以下表，無需修改：

| ClickHouse 表 | MSSQL 來源 | 同步方式 |
|---------------|------------|----------|
| `bronze.bpm_act_hi_procinst` | `ACT_HI_PROCINST` | 增量 |
| `bronze.bpm_act_hi_taskinst` | `ACT_HI_TASKINST` | 增量 |
| `bronze.bpm_act_hi_varinst` | `ACT_HI_VARINST` | 增量 |
| `bronze.bpm_act_re_procdef` | `ACT_RE_PROCDEF` | 全量 |
| `bronze.common_hr_employee` | `HR_Employee` | 全量 |

### 2.2 Silver 層設計

#### 2.2.1 流程變數寬表 (Pivot)

```sql
-- silver.varinst_process_pivot
-- 用途：將流程層級變數從 EAV 轉成寬表
CREATE TABLE silver.varinst_process_pivot
(
    proc_inst_id String,
    plant Nullable(String),
    factory Nullable(String),
    production_area Nullable(String),
    line_name Nullable(String),
    model_name Nullable(String),
    delivery_area Nullable(String),
    schedule_number Nullable(String),
    mo_number Nullable(String),
    sap_plant Nullable(String),
    sap_product_group Nullable(String),
    pallet Nullable(String),
    transfer_no Nullable(String),
    q_block_event_id Nullable(String),
    defect_sn Nullable(String),
    time_key Nullable(String),
    region Nullable(String),
    _transform_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_transform_time)
ORDER BY (proc_inst_id)
SETTINGS index_granularity = 8192;
```

**取值規則**：同 `PROC_INST_ID_` + `NAME_` 多筆時，取 `MAX(TEXT_)`

#### 2.2.2 Task 變數寬表 (Pivot)

```sql
-- silver.varinst_task_pivot
-- 用途：將 Task 層級變數從 EAV 轉成寬表
CREATE TABLE silver.varinst_task_pivot
(
    task_id String,
    auto_complete Nullable(Int64),  -- LONG_ 值，1=bypass, 0=非bypass
    _transform_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_transform_time)
ORDER BY (task_id)
SETTINGS index_granularity = 8192;
```

#### 2.2.3 任務明細寬表（核心 Silver 表）

```sql
-- silver.task_detail_wide
-- 用途：任務明細寬表，等價於 Reference SQL 的子查詢
CREATE TABLE silver.task_detail_wide
(
    -- 主鍵
    task_id String,
    
    -- 流程資訊
    proc_inst_id String,
    proc_def_id Nullable(String),
    process_definition_key Nullable(String),
    process_definition_name Nullable(String),
    delete_reason Nullable(String),
    
    -- 任務資訊
    task_definition_key Nullable(String),
    task_name Nullable(String),
    task_status LowCardinality(String),  -- TODO/DOING/DONE
    task_bypass LowCardinality(String),  -- Y/N
    task_assignee Nullable(String),
    task_assignee_account Nullable(String),
    task_assignee_name Nullable(String),
    
    -- 時間欄位
    task_create_time DateTime64(3),
    task_claim_time Nullable(DateTime64(3)),
    task_end_time Nullable(DateTime64(3)),
    task_create_date Date,
    
    -- 計算欄位
    task_duration_minutes Nullable(Float64),
    task_work_minutes Nullable(Float64),
    
    -- 流程變數（維度）
    plant Nullable(String),
    factory Nullable(String),
    production_area Nullable(String),
    line Nullable(String),
    model_name Nullable(String),
    delivery_area Nullable(String),
    schedule_number Nullable(String),
    mo_number Nullable(String),
    sap_plant Nullable(String),
    sap_product_group Nullable(String),
    pallet Nullable(String),
    transfer_no Nullable(String),
    q_block_event_id Nullable(String),
    defect_sn Nullable(String),
    time_key Nullable(String),
    region Nullable(String),
    
    -- Metadata
    _transform_time DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(_transform_time)
PARTITION BY toYYYYMM(task_create_date)
ORDER BY (task_create_date, plant, line, task_id)
SETTINGS index_granularity = 8192;
```

### 2.3 Gold 層設計

Gold 層可直接查詢 Silver 層，或建立預聚合表（視需求）。

---

## 3. Silver 層 ETL SQL

### 3.1 流程變數 Pivot SQL

```sql
INSERT INTO silver.varinst_process_pivot
SELECT 
    PROC_INST_ID_ AS proc_inst_id,
    MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS plant,
    MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS factory,
    MAX(CASE WHEN NAME_ = 'productionArea' THEN TEXT_ END) AS production_area,
    MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS line_name,
    MAX(CASE WHEN NAME_ = 'modelName' THEN TEXT_ END) AS model_name,
    MAX(CASE WHEN NAME_ = 'deliveryArea' THEN TEXT_ END) AS delivery_area,
    MAX(CASE WHEN NAME_ = 'scheduleNumber' THEN TEXT_ END) AS schedule_number,
    MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS mo_number,
    MAX(CASE WHEN NAME_ = 'sapPlant' THEN TEXT_ END) AS sap_plant,
    MAX(CASE WHEN NAME_ = 'sapProductGroup' THEN TEXT_ END) AS sap_product_group,
    MAX(CASE WHEN NAME_ = 'pallet' THEN TEXT_ END) AS pallet,
    MAX(CASE WHEN NAME_ = 'transferNo' THEN TEXT_ END) AS transfer_no,
    MAX(CASE WHEN NAME_ = 'qBlockEventId' THEN TEXT_ END) AS q_block_event_id,
    MAX(CASE WHEN NAME_ = 'defectSn' THEN TEXT_ END) AS defect_sn,
    MAX(CASE WHEN NAME_ = 'time' THEN concat('_', TEXT_) END) AS time_key,
    MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region,
    now64(3) AS _transform_time
FROM bronze.bpm_act_hi_varinst FINAL
WHERE NAME_ IN (
    'plant', 'factory', 'productionArea', 'lineName', 'modelName',
    'deliveryArea', 'scheduleNumber', 'moNumber', 'sapPlant', 'sapProductGroup',
    'pallet', 'transferNo', 'qBlockEventId', 'defectSn', 'time', 'region'
)
  AND PROC_INST_ID_ IS NOT NULL
  AND PROC_INST_ID_ != ''
GROUP BY PROC_INST_ID_;
```

### 3.2 Task 變數 Pivot SQL

```sql
INSERT INTO silver.varinst_task_pivot
SELECT 
    TASK_ID_ AS task_id,
    MAX(LONG_) AS auto_complete,
    now64(3) AS _transform_time
FROM bronze.bpm_act_hi_varinst FINAL
WHERE NAME_ = 'autoComplete'
  AND TASK_ID_ IS NOT NULL
  AND TASK_ID_ != ''
GROUP BY TASK_ID_;
```

### 3.3 任務明細寬表 ETL SQL

```sql
INSERT INTO silver.task_detail_wide
SELECT 
    -- 主鍵
    hti.ID_ AS task_id,
    
    -- 流程資訊
    hti.PROC_INST_ID_ AS proc_inst_id,
    hti.PROC_DEF_ID_ AS proc_def_id,
    pd.KEY_ AS process_definition_key,
    pd.NAME_ AS process_definition_name,
    hi.DELETE_REASON_ AS delete_reason,
    
    -- 任務資訊
    hti.TASK_DEF_KEY_ AS task_definition_key,
    hti.NAME_ AS task_name,
    CASE
        WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
        WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
        ELSE 'TODO'
    END AS task_status,
    CASE WHEN COALESCE(vt.auto_complete, 0) = 1 THEN 'Y' ELSE 'N' END AS task_bypass,
    hti.ASSIGNEE_ AS task_assignee,
    he.ADAccount AS task_assignee_account,
    he.EmpName AS task_assignee_name,
    
    -- 時間欄位
    hti.START_TIME_ AS task_create_time,
    hti.CLAIM_TIME_ AS task_claim_time,
    hti.END_TIME_ AS task_end_time,
    toDate(hti.START_TIME_) AS task_create_date,
    
    -- 計算欄位
    CASE
        WHEN hti.END_TIME_ IS NOT NULL THEN
            round(dateDiff('second', hti.START_TIME_, hti.END_TIME_) / 60.0, 2)
        ELSE
            round(dateDiff('second', hti.START_TIME_, now()) / 60.0, 2)
    END AS task_duration_minutes,
    CASE
        WHEN hti.CLAIM_TIME_ IS NULL THEN 0
        WHEN hti.END_TIME_ IS NOT NULL THEN
            round(dateDiff('second', hti.CLAIM_TIME_, hti.END_TIME_) / 60.0, 2)
        ELSE
            round(dateDiff('second', hti.CLAIM_TIME_, now()) / 60.0, 2)
    END AS task_work_minutes,
    
    -- 流程變數（維度）
    vp.plant,
    vp.factory,
    vp.production_area,
    vp.line_name AS line,
    vp.model_name,
    vp.delivery_area,
    vp.schedule_number,
    vp.mo_number,
    vp.sap_plant,
    vp.sap_product_group,
    vp.pallet,
    vp.transfer_no,
    vp.q_block_event_id,
    vp.defect_sn,
    vp.time_key,
    vp.region,
    
    -- Metadata
    now64(3) AS _transform_time
FROM bronze.bpm_act_hi_taskinst hti FINAL
INNER JOIN bronze.bpm_act_hi_procinst hi FINAL ON hti.PROC_INST_ID_ = hi.PROC_INST_ID_
LEFT JOIN bronze.bpm_act_re_procdef pd FINAL ON hti.PROC_DEF_ID_ = pd.ID_
LEFT JOIN silver.varinst_process_pivot vp ON hti.PROC_INST_ID_ = vp.proc_inst_id
LEFT JOIN silver.varinst_task_pivot vt ON hti.ID_ = vt.task_id
LEFT JOIN bronze.common_hr_employee he FINAL ON hti.ASSIGNEE_ = he.EmpCode;
```

---

## 4. Gold 層查詢 SQL

### 4.1 等價查詢（驗證用）

```sql
-- 等價於 Reference SQL 的查詢
SELECT 
    task_id,
    task_status,
    task_bypass,
    plant,
    line,
    factory,
    task_create_time
FROM silver.task_detail_wide FINAL
WHERE task_create_date = '2025-12-31'
  AND task_bypass = 'N'
  AND plant = 'WJ2'
  AND line = 'E5'
ORDER BY task_create_time;
```

### 4.2 對帳驗證方式

```sql
-- 1. 總筆數驗證
SELECT count(*) FROM silver.task_detail_wide FINAL
WHERE task_create_date = '2025-12-31'
  AND task_bypass = 'N'
  AND plant = 'WJ2'
  AND line = 'E5';
-- 預期: 12

-- 2. 狀態分布驗證
SELECT task_status, count(*) 
FROM silver.task_detail_wide FINAL
WHERE task_create_date = '2025-12-31'
  AND task_bypass = 'N'
  AND plant = 'WJ2'
  AND line = 'E5'
GROUP BY task_status;
-- 預期: TODO=8, DOING=2, DONE=2

-- 3. TaskId 清單驗證
SELECT task_id FROM silver.task_detail_wide FINAL
WHERE task_create_date = '2025-12-31'
  AND task_bypass = 'N'
  AND plant = 'WJ2'
  AND line = 'E5'
ORDER BY task_id;
```

---

## 5. 現有表對齊與變更清單

### 5.1 現有表命名對照

| 現有表 | 建議保留/修改 | 說明 |
|--------|---------------|------|
| `bronze.bpm_act_hi_*` | 保留 | Bronze 層已正確同步 |
| `bronze.common_flowable_task_stats` | **不使用** | 此表是 MSSQL 預計算表，ClickHouse 應從原始表計算 |
| `silver.FACT_TASK_VX_ATTRIBUTION` | 保留 | 用於 L5 指標，與本次需求不衝突 |

### 5.2 需新增的表

| 表名 | 用途 |
|------|------|
| `silver.varinst_process_pivot` | 流程變數寬表 |
| `silver.varinst_task_pivot` | Task 變數寬表 |
| `silver.task_detail_wide` | 任務明細寬表（核心） |

### 5.3 ETL 調整點

1. 新增 Silver 層轉換腳本：`scripts/transform_silver_task_detail.py`
2. 新增 DDL：`sql/10_create_silver_task_detail.sql`
3. 建立定期刷新機制（增量或全量）

### 5.4 對帳驗證結果

執行 `scripts/verify_clickhouse_vs_mssql.py` 驗證結果：

```
====================================================================================================
3. 對帳結果
====================================================================================================

筆數比較:
  MSSQL:      12
  ClickHouse: 12
  差異:       0

TaskId 比較:
  只在 MSSQL:      0
  只在 ClickHouse: 0

狀態分布比較:
  DOING: MSSQL=2, ClickHouse=2 ✓
  DONE: MSSQL=2, ClickHouse=2 ✓
  TODO: MSSQL=8, ClickHouse=8 ✓

====================================================================================================
✅ 對帳通過！MSSQL 與 ClickHouse 結果完全一致
====================================================================================================
```

---

## 6. 風險點與對策

| 風險 | 說明 | 對策 |
|------|------|------|
| **VARINST 同名多筆** | 同 `PROC_INST_ID_` + `NAME_` 可能有多筆 | 使用 `MAX(TEXT_)` 取值 |
| **流程變數 vs Task 變數混用** | `autoComplete` 是 Task 層級，其他是流程層級 | 分開 Pivot，JOIN Key 不同 |
| **JOIN 倍增** | 多對多 JOIN 可能造成筆數膨脹 | Pivot 後 1:1 JOIN，用 `count(*)` vs `countDistinct(task_id)` 驗證 |
| **時間欄位型別** | MSSQL `datetime2` vs ClickHouse `DateTime64` | 統一使用 `DateTime64(3)` |
| **bypass NULL 規則** | `autoComplete` 不存在時應視為 `N` | 使用 `COALESCE(auto_complete, 0)` |
| **ReplacingMergeTree 未合併** | 查詢時可能有重複 | 查詢時加 `FINAL` 關鍵字 |
