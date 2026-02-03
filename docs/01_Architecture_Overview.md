# DMP Flowable 架構總覽

> **文件版本**: v2.1 (架構優化版)  
> **最後更新**: 2026-02-03  
> **架構類型**: Bronze/Silver/Gold 三層資料倉儲 + ClickHouse 原生自動化


---

## 架構圖

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MSSQL 來源系統                                │
│  ┌────────────────────────────┐  ┌────────────────────────────────┐ │
│  │ APP_SRV_BPM               │  │ APP_SRV_COMMON                 │ │
│  │ • ACT_HI_TASKINST         │  │ • HR_Employee                  │ │
│  │ • ACT_HI_VARINST          │  │ • MDM_* (主檔)                 │ │
│  │ • ACT_HI_PROCINST         │  │                                │ │
│  └────────────────────────────┘  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ Python 同步腳本 (增量/全量)
┌─────────────────────────────────────────────────────────────────────┐
│  Bronze 層 (原始資料)           ClickHouse 10.136.218.207:8121      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ • bpm_act_hi_taskinst  (任務實例，增量同步)                     ││
│  │ • bpm_act_hi_varinst   (流程變數，增量同步)                     ││
│  │ • common_hr_employee   (員工，全量同步)                         ││
│  │ • common_mdm_*         (MDM 主檔，全量同步)                     ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ Materialized View (Bronze INSERT 觸發)
┌─────────────────────────────────────────────────────────────────────┐
│  Silver 層 (清洗轉換)                                               │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Layer 1:                                                        ││
│  │ • mv_varinst_pivoted      (Refreshable 每小時自動刷新)          ││
│  │ • mv_dim_mfg_five_level   (五階維度，MDM 整合版)                ││
│  │                                                                 ││
│  │ Layer 2:                                                        ││
│  │ • mv_fact_task_vx         (核心事實表，多時間維度版本)          ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘

                                  │
                                  ▼ Refreshable MView (每小時自動刷新)
┌─────────────────────────────────────────────────────────────────────┐
│  Gold 層 (指標快照)                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ • rmv_l5_task_completion  (L5 任務完成率，REFRESH EVERY 1 HOUR) ││
│  │ • rmv_user_utilization    (人員使用率，REFRESH EVERY 1 HOUR)    ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  應用層                                                             │
│  • Cube.js 語意層 API                                               │
│  • 儀表板 / 報表                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 關鍵表清單

### Bronze 層 (原始資料)

| 表名 | 來源 | 同步方式 | 說明 |
|------|------|---------|------|
| `bpm_act_hi_taskinst` | ACT_HI_TASKINST | 增量 | 任務實例 |
| `bpm_act_hi_varinst` | ACT_HI_VARINST | 增量 | 流程變數 |
| `common_hr_employee` | HR_Employee | 全量 | 員工主檔 |
| `common_mdm_*` | MDM_* | 全量 | 五階維度主檔 |

### Silver 層 (Materialized View)

| 表名 | 來源 | 更新機制 | 說明 |
|------|------|---------|------|
| `mv_varinst_pivoted` | bpm_act_hi_varinst | **REFRESH EVERY 1 HOUR** | EAV 轉置 |
| `mv_dim_mfg_five_level` | common_mdm_* | POPULATE | 五階維度 (修正 MDM 路徑) |
| `mv_fact_task_vx` | 上述表 JOIN | POPULATE | 核心事實表 (100% 對齊) |


### Gold 層 (Refreshable MView)

| 表名 | 來源 | 更新機制 | 說明 |
|------|------|---------|------|
| `rmv_l5_task_completion` | mv_fact_task_vx | **REFRESH EVERY 1 HOUR** | L5 完成率 |
| `rmv_user_utilization` | mv_fact_task_vx | **REFRESH EVERY 1 HOUR** | 人員使用率 |

---

## 自動化機制

### ClickHouse 原生 Refreshable MView

```sql
CREATE MATERIALIZED VIEW gold.rmv_l5_task_completion
REFRESH EVERY 1 HOUR  -- 每小時自動刷新
ENGINE = ReplacingMergeTree(_refresh_time)
...
```

- **無需外部排程** (Airflow/Cron)
- **ClickHouse 內建調度器**自動執行
- **資料保留 1 年** (TTL 設定)

---

## 業務邏輯

### Vx 歸屬規則 (Silver 層實作)

```sql
CASE 
    WHEN moNumber LIKE '315%' THEN 'V1'  -- 工單號規則優先
    WHEN moNumber LIKE '196%' OR '199%' OR '200%' ... THEN 'V1'
    WHEN taskDefinitionKey LIKE 'V1%' THEN 'V1'
    WHEN taskDefinitionKey LIKE 'V2%' THEN 'V2'
    WHEN taskDefinitionKey LIKE 'V3%' THEN 'V3'
    ELSE 'Unknown'
END AS vx_type
```

### 排除規則

- `is_excluded = 1` 當：
  - TaskBypass = 'Y' (autoComplete)
  - TaskDefinitionKey 以 'E' 或 'C' 開頭
  - moNumber 以 'Q' 或 'R' 開頭

---

## SQL 檔案位置

| 檔案 | 說明 |
|------|------|
| `sql/rebuild/01_bronze_add_ttl.sql` | Bronze 層 TTL 設定 |
| `sql/rebuild/02_bronze_common_dims.sql` | Bronze 維度表同步 |
| `sql/rebuild/03_silver_pivot_and_hierarchy.sql` | Silver L1 (透視表 + 維度) |
| `sql/rebuild/04_silver_fact_tasks.sql` | Silver L2 (核心事實表) |
| `sql/rebuild/06_gold_kpi_task_completion.sql` | Gold 層 L5 完成率 |
| `sql/rebuild/07_gold_kpi_user_utilization.sql` | Gold 層 L7 人員使用率 |


---

## 相關文件

- [metric_definitions.md](metric_definitions.md) - 指標業務定義
- [flowable_task_stats_mapping.md](flowable_task_stats_mapping.md) - 欄位對應
- [memory-bank/systemPatterns.md](../memory-bank/systemPatterns.md) - 技術決策
