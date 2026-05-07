# 系統架構模式 - DMP Flowable

## 資料流架構

```
MSSQL (APP_SRV_BPM, APP_SRV_COMMON)
         │
         ▼ sync/ 同步腳本 (Python + Native ODBC)
         │
    ┌────┴────┐
    │ Bronze  │  原始資料層 (18 張表，ReplacingMergeTree)
    │ 層      │  - bpm_act_hi_taskinst
    └────┬────┘  - bpm_act_hi_varinst
         │       
    ┌────┴────┐
    │ Silver  │  超級事實層 (Super Silver Architecture - V4.3)
    │ 層      │  - mv_varinst_pivoted (變數攤平，含 11 業務變數)
    │         │  - mv_fact_task_vx (統一事實表：含 L4, 變數, 時效, 標籤)
    └────┬────┘  
         │       
    ┌────┴────┐
    │ Gold    │  指標聚合層 (Physical Snapshot Tables - V4.2)
    │ 層      │  - gold.rmv_l5_task_completion_phys (多粒度 Bitmap)
    │         │  - gold.rmv_l5_acc_phys (累計指標)
    └────┬────┘  
         │
    ┌─────────┐
    │ Cube.js │  語意層 (L5TaskDetailsSuper 用於明細鑽取)
    └─────────┘
```

## 關鍵技術決策

### 1. 超級事實表大統一 (V4.3 - 2026-04-29)
- **決策**: 將原本獨立的「UI 明細表」整合進核心 `mv_fact_task_vx`。
- **優點**: 
    1. **單一真相來源**: 報表指標與明細數據保證 100% 邏輯一致。
    2. **簡化維護**: 只需要維護一組 DML 與回填腳本。
- **欄位標準**: 包含 L4 流程 ID、11 個業務變數 (MoNumber, ModelName 等)、分鐘級時效指標、以及三層結算標籤 (Daily/Weekly/Monthly)。

### 2. DML 去重關聯模式 (argMax Pattern)
- **問題**: 關聯 `ReplacingMergeTree` 類型的變數攤平表時，若資料尚未合併，會導致任務行數翻倍（Join Multiplication）。
- **解法**: 
    - 使用 `argMax(value, refresh_time)` 搭配 `GROUP BY PROC_INST_ID_`。
    - 確保每一個任務僅關聯到該流程最新、唯一的變數版本。
- **效能考量**: 雖然 `argMax` 消耗記憶體，但能保證在不使用 `FINAL` 的情況下數據精確，大幅提升前端查詢穩定性。

### 3. VTYPE 分類邏輯 (315 修正)
- **規則**: 對於工單號開頭為 '196', '199', '200', '210', '212', '213', **'315'** 的任務，強制歸類為 `V1`。
- **實作**: 使用 `substring(COALESCE(v_pivot.varinst_moNumber, ''), 1, 3)` 進行匹配。

### 4. 計算架構 (Windowed Computation)
- **實作**: 透過 `ops_metrics.etl_checkpoint` 記錄進度。
- **Reset 機制**: 實作 `--reset` 參數，用於清空檢查點並執行完整重建。
- **低記憶體優化**: 針對 6GB RAM 環境，採用 7-15 天一組的步進視窗，配合 `low-ram` 設定降低併發。

### 5. 多粒度梯次標籤 (Multi-Granularity Cohort)
- **邏輯**: 每個任務在 Silver 層預計算 `status_daily`, `status_weekly`, `status_monthly`。
- **用途**: 支援 Gold 層按不同週期粒度進行 Bitmap 聚合，解決跨週期狀態偏移問題。

### 6. 指標分母對齊模式 (Denominator Alignment - 2026-05-07)
- **問題**: `Acc Rate` (積壓率) 分母若採用「當日開單量」，在週末或低產量日會因分母極小導致數據飆升至數倍。
- **解法**: 
    - **日維度**: 分母改用 **7 日滾動總開單量 (`acc_total_task`)**，使分子分母時間窗口一致。
    - **週/月維度**: 採用 **週期結算邏輯**，公式切換為 `(todo + doing) / total_task`。
- **實作**: 在 Cube.js 中使用 `CASE WHEN any(granularity) = 'Day' THEN ...` 實作維度感知 (Dimension-Aware) 指標。

## Cube.js 設計模式

### 1. L5TaskDetailsSuper (超級明細鑽取)
- **模式**: 直接映射 `silver.mv_fact_task_vx` 的 41 個欄位。
- **功能**: 支援從高層 KPI (Gold) 直接鑽取至最底層的工單、機種與分配人員。

### 2. Time Machine & Filter Isolation (時光機模式)
- **解法**: 使用 `anchor_dt` 與實體日期分離，確保跨年與跨週資料能被正確 Filter。
- **ISO 字串修正**: 全面採用 `formatDateTime(..., '%Y-%m-%d')` 避免 ClickHouse 24.3 的 DateTime 轉型報錯。

## 🚨 關鍵安全規則
> [!DANGER]
> **嚴禁刪除任何 MSSQL 表格**
> - 來源資料庫為生產環境。
> 
> [!WARNING]
> **ClickHouse 毀滅性操作規範**
> - `DROP TABLE` 或 `TRUNCATE TABLE` 必須在 `execute_etl.py --reset` 或手動執行前確認受影響範圍。
