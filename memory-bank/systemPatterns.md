# 系統架構模式 - DMP Flowable

## 資料流架構

```
MSSQL (APP_SRV_BPM, APP_SRV_COMMON)
         │
         ▼ sync/ 同步腳本 (Python)
         │
    ┌────┴────┐
    │ Bronze  │  原始資料層 (18 張表)
    │ 層      │  - bpm_act_hi_taskinst
    └────┬────┘  - bpm_act_hi_varinst
         │       - common_hr_employee
         ▼       - common_mdm_* (主檔)
    ┌────┴────┐
    │ Silver  │  清洗轉換層 (4 張 RMV)
    │ 層      │  - mv_varinst_pivoted (變數透視)
    └────┬────┘  - mv_dim_mfg_five_level (五階維度)
         │       - mv_fact_task_vx (核心事實表)
         ▼
    ┌────┴────┐
    │ Gold    │  指標快照層 (2 張 RMV)
    │ 層      │  - rmv_l5_task_completion (L5 完成率)
    └────┬────┘  - rmv_user_utilization (人員使用率)
         │
         ▼
    ┌────┴────┐
    │ Cube.js │  語意層 API
    └─────────┘
```

## 關鍵技術決策

### 1. 為什麼用 Refreshable MView 而非原生增量 MView？
- ClickHouse 原生 MView 只在主表 INSERT 時觸發
- JOIN 表更新時不會觸發 MView 刷新
- 使用 `REFRESH EVERY 1 HOUR` 確保資料一致性

### 2. 資料保留策略
- 使用 TTL 設定：`TTL snapshot_date + INTERVAL 1 YEAR`
- 資料保留 365 天

### 3. 重複資料處理
- 使用 `ReplacingMergeTree` 引擎
- 查詢時使用 `FINAL` 關鍵字確保資料一致
