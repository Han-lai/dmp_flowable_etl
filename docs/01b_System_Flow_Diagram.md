# 資料管道流程圖

> **版本**: v2.1 (架構優化版)  
> **最後更新**: 2026-02-09  
> **架構類型**: 單路徑 + ClickHouse 原生 Refreshable MView


---

## 完整資料流

```
┌──────────────────────────────────────────────────────────────────────┐
│                         MSSQL 來源系統                               │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ APP_SRV_BPM                                                     │ │
│  │ - ACT_HI_TASKINST (任務實例)     ← L5 任務主要來源              │ │
│  │ - ACT_HI_VARINST (流程變數)      ← plant/factory/line/moNumber  │ │
│  │ - ACT_HI_PROCINST (流程實例)                                    │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ APP_SRV_COMMON                                                  │ │
│  │ - HR_Employee (員工)                                            │ │
│  │ - MDM_MFG_SITE_MASTER (地區主檔)                                │ │
│  │ - MDM_FACTORY_AREA_MASTER (工廠主檔)                            │ │
│  │ - MDM_PROD_AREA_MASTER (產區主檔)                               │ │
│  │ - MDM_LINE_DESC_MASTER (產線主檔)                               │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
        ┌─────────────────────┐   ┌─────────────────────┐
        │  增量同步 (大表)    │   │  全量同步 (小表)    │
        │  - 5 張 BPM 表      │   │  - 13 張主檔表     │
        │  - 基於時間戳追蹤   │   │  - 每日完全覆蓋    │
        └─────────────────────┘   └─────────────────────┘
                    │                         │
                    └────────────┬────────────┘
                                 │
                                 ▼
        ┌──────────────────────────────────────────────────────────┐
        │              Bronze 層 (原始資料層)                      │
        │  ClickHouse 10.136.218.207:8121                          │
        │                                                          │
        │  ┌─────────────────────────────────────────────────────┐ │
        │  │ BPM 表 (增量同步)                                   │ │
        │  │ - bpm_act_hi_taskinst  (任務實例)                   │ │
        │  │ - bpm_act_hi_varinst   (流程變數)                   │ │
        │  │ - bpm_act_hi_procinst  (流程實例)                   │ │
        │  └─────────────────────────────────────────────────────┘ │
        │  ┌─────────────────────────────────────────────────────┐ │
        │  │ 主檔表 (全量同步)                                   │ │
        │  │ - common_hr_employee   (員工)                       │ │
        │  │ - common_mdm_*         (MDM 五階維度主檔)           │ │
        │  └─────────────────────────────────────────────────────┘ │
        │  ┌─────────────────────────────────────────────────────┐ │
        │  │ 系統表                                              │ │
        │  │ - _sync_watermark      (同步水位線)                 │ │
        │  └─────────────────────────────────────────────────────┘ │
        └──────────────────────────────────────────────────────────┘
                                 │
                                 ▼ 混合觸發 (MView + Refreshable)

        ┌──────────────────────────────────────────────────────────┐
        │              Silver 層 (轉換層)                          │
        │                                                          │
        │  ┌─────────────────────────────────────────────────────┐ │
        │  │ Layer 1: 基礎聚合                                   │ │
        │  │ - mv_varinst_pivoted      (Refreshable 每小時)     │ │
        │  │ - mv_dim_mfg_five_level   (MDM 整合版)              │ │
        │  └─────────────────────────────────────────────────────┘ │

        │                         │                                │
        │                         ▼                                │
        │  ┌─────────────────────────────────────────────────────┐ │
        │  │ Layer 2: 核心事實表                                 │ │
        │  │ - mv_fact_task_vx         (L5 任務事實表)          │ │
        │  │   ├─ Vx 歸屬邏輯 (Key > moNumber)                   │ │
        │  │   ├─ Task Status (TODO/DOING/DONE)                 │ │
        │  │   ├─ 五階維度 (Region/Plant/Factory/Line)          │ │
        │  │   └─ 排除標記 (bypass/E/C)                         │ │
        │  └─────────────────────────────────────────────────────┘ │
        └──────────────────────────────────────────────────────────┘
                                 │
                                 ▼ Refreshable MView (每小時自動刷新)
        ┌──────────────────────────────────────────────────────────┐
        │              Gold 層 (指標快照層)                        │
        │                                                          │
        │  - rmv_l5_task_completion    (L5 任務完成率)            │
        │    └─ REFRESH EVERY 1 HOUR ⏰                            │
        │                                                          │
        │  - rmv_user_utilization      (人員使用率)               │
        │    └─ REFRESH EVERY 1 HOUR ⏰                            │
        │                                                          │
        │  資料保留: TTL 1 YEAR                                    │
        └──────────────────────────────────────────────────────────┘
                                 │
                                 ▼
        ┌──────────────────────────────────────────────────────────┐
        │              應用層 (儀表板/報表)                        │
        │                                                          │
        │  - Cube.js (語意層 API)                                  │
        │  - Superset (儀表板)                                     │
        │  - 報表系統                                              │
        └──────────────────────────────────────────────────────────┘
```

---

## 資料更新流程

```
時間軸:
├─ T0: Bronze 同步完成
│   ├─ Python 腳本執行增量/全量同步
│   └─ bpm_act_hi_* 表更新
│
├─ T1: Silver Layer 1 異步刷新
│   ├─ mv_varinst_pivoted (每小時刷新，合併流程變量)
│   └─ mv_dim_mfg_five_level (MDM 異動時刷新)
│
├─ T2: Silver Layer 2 自動更新
│   └─ mv_fact_task_vx 觸發更新 (依賴 L1 完備性)

│
├─ T3: Gold 層刷新 (每小時)
│   ├─ rmv_l5_task_completion 自動刷新
│   └─ rmv_user_utilization 自動刷新
│
└─ T4: 應用層查詢可用
    └─ 儀表板/報表更新
```

---

## 與舊架構差異

| 項目 | 舊架構 (Path A/B) | 新架構 (Rebuild) |
|------|------------------|------------------|
| **Silver 層** | Path A: 直接表 + Path B: 8 張 MVIEW | 單路徑: 3 張 MVIEW |
| **資料來源** | FlowableTaskStats (聚合表) | bpm_act_hi_taskinst (原生表) |
| **Gold 層更新** | 手動腳本 + Airflow 排程 | **Refreshable MView 自動** |
| **維護複雜度** | 高 (雙路徑) | 低 (單路徑) |

---

## SQL 檔案位置

| 檔案 | 順序 | 說明 |
|------|------|------|
| `sql/rebuild/01_bronze_add_ttl.sql` | 1 | Bronze 層 TTL |
| `sql/rebuild/02_bronze_common_dims.sql` | 2 | Bronze 維度表同步 |
| `sql/rebuild/03_silver_pivot_and_hierarchy.sql` | 3 | Silver L1 (透視表 + 維度) |
| `sql/rebuild/04_silver_fact_tasks.sql` | 4 | Silver L2 (核心事實表) |
| `sql/rebuild/06_gold_kpi_task_completion.sql` | 5 | Gold 層 (Refreshable) |


---

## 故障排除

### Gold 層未更新

```sql
-- 檢查 Refreshable MView 狀態
SELECT database, name, engine
FROM system.tables 
WHERE database = 'gold' AND name LIKE 'rmv_%';

-- 手動觸發刷新
SYSTEM REFRESH VIEW gold.rmv_l5_task_completion;
```

### Silver 層查詢緩慢

```sql
-- 使用 FINAL 確保資料一致性
SELECT * FROM silver.mv_fact_task_vx FINAL
WHERE task_start_date = today();

-- 強制資料合併
OPTIMIZE TABLE silver.mv_fact_task_vx FINAL;
```

---

**文件更新時間**: 2026-02-09
