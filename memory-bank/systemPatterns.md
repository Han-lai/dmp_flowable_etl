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
    │ Gold    │  指標聚合層 (ReplacingMergeTree + VIEW)
    │ 層      │  - rmv_l5_task_completion (L5 完成率)
    └────┬────┘  - rmv_user_utilization (人員使用率)
         │
         ▼
    ┌─────────┐
    │ Cube.js │  語意層 API (與 Superset 整合)
    └─────────┘
          │
          ▼
    ┌─────────┐
    │ FastAPI │  進階報表 API (自定義複雜格式)
    └─────────┘
```

## 關鍵技術決策

### 1. 為什麼用 Refreshable MView 而非原生增量 MView？
- ClickHouse 原生 MView 只在主表 INSERT 時觸發
- JOIN 表更新時不會觸發 MView 刷新
- 使用 `REFRESH EVERY 48 HOUR` 確保資料一致性 (2026-02-12 調整)
- **注意**: 多層級 MView (Silver -> Gold) 刷新存在延遲，執行全量重建腳本時需加入等待緩衝 (`sleep`) 以避免讀取空資料。

### 2. 資料保留策略
- 使用 TTL 設定：`TTL snapshot_date + INTERVAL 1 YEAR`
- 資料保留 365 天

### 3. Checkpoint-based Computation (故障自癒計算模式)
- **定義**: 在 Python (`execute_etl.py`) 中透過 `bronze.etl_checkpoint` 記錄每個運算時間視窗的狀態。
- **實作**: 
    - 階段區分：分為 `silver_varinst_pivoted` 與 `gold_task_completion`。
    - 斷點續傳：程式失敗後重新執行，自動跳過已成功的視窗。
    - **重刷機制**: 透過 `--reset` 或 `--backfill` 指定時間區間，配合 `ReplacingMergeTree` 實現冪等更新。

### 4. 重複資料處理
- 使用 `ReplacingMergeTree` 引擎。
- 原則：**以同步版本 (`_sync_version`) 作為版本號**，確保多次同步後僅保留最新資料，消滅 DELETE 導致的性能負擔。
 
### 5. 指標計算與對齊模式 (Metric & Parity Patterns)
- **Any-Event Filter**: 為了與 Baseline 核對，不僅統計 Task 節點，還納入所有在 `ACT_HI_TASKINST` 中有活動記錄的關聯事件。
- **180 天變數回溯 (Variable Lookback)**: 針對跨月長週期任務，回溯 180 天內的流程變數，確保 Region/Plant 等維度不缺失。
- **金層實體表與視圖 (Gold 2-Tier Architecture)**: 
    - `gold.rmv_l5_task_completion_phys`: 實體表，使用 **`ReplacingMergeTree`** 儲存冪等快照，避免歷史回補時發生 Double-count 和 OOM。
    - `gold.rmv_l5_task_completion`: 對接視圖，整合實體表數據並提供最終防禦性去重給 Cube.js/Superset，實現「數據與流量隔離」。
- **ACC 滾動脫鉤 (ACC Decoupling)**: 7 天滾動指標 (ACC) 因涉及 `uniqExact` 的跨天去重，不再與 Todo/Doing/Done 的每日快照混合聚合，而是透過獨立的 `acc_stats` CTE 搭配 `range()` 展開計算，以確保 Baseline 完全精準對齊。

## Cube.js 設計模式 (Design Patterns)

### 1. Logic Push-down (SQL 下沉模式)
*   **定義**: 將複雜的資料處理邏輯 (如日期計算、Union) 從 Cube 的 JS 層移至底層 SQL (CTE)。
*   **優點**: 高效能、邏輯可複用、Cube 模型極簡化。

### 2. Time Machine & Filter Isolation (時光機與篩選分離)
*   **問題**: 直接篩選日期會濾除回溯所需的歷史資料。
*   **解法**: 
    *   **SQL 層**: `anchor_dt as filter_date` (固定值) 與 `snapshot_date_real` (變動值)。
    *   **Cube 層**: `snapshotDate` 映射到 `filter_date` 用於接收 Filter；`realSnapshotDate` 顯示真實日期。
*   **關鍵細節 (ISO Date Fix)**: 
    *   Dashboard Filter 會帶入 ISO 格式 (`T00:00:00Z`)。
    *   **對策**: 維度設為 `type: string` 並用 `formatDateTime(..., '%Y-%m-%d')` 對齊。

### 3. Filter List Exposure (過濾器清單擴張)
*   **技術**: 在 SQL 加入 `UNION ALL SELECT DISTINCT snapshot_date`。
*   **用途**: 讓下拉選單能顯示所有可用日期，而非僅限於目前計算出的 Anchor Date。

## FastAPI 設計模式 (API Design Patterns)

### 1. Dynamic Period Aggregation (動態週期聚合)
*   **模式**: 在 API 層動態計算報表所需的時間軸（如最後 7 天、最後 3 個 ISO 週、月結尾）。
*   **實作**: 利用 Python `datetime` 與 `calendar` 模組產生日期清單，並使用 SQL `UNION ALL` 一次性從 ClickHouse 撈取多個維度的聚合數據。

### 2. Status Breakdown Mapping (狀態分解映射)
*   **模式**: 將資料庫中的基本 Status (Todo, Doing, Done) 在 API 層組合成業務所需的進階指標（如 Doing+Done, Acc）。
*   **實作**: 提供 Qty 與 Percentage 的雙重映射結構，方便前端直接渲染。

### 3. Containerized Deployment (容器化部署: Split-Stack)
*   **模式**: 將 ClickHouse 與 API 服務解耦，統一整合於 `infra/` 目錄下進行管理。
*   **管理網域 (Infra Center)**: 使用 `infra/docker-compose.yml` 管理資料倉儲，`infra/docker-compose-api.yml` 管理 API。
*   **動態掛載 (Dynamic Runtime)**: API 採用 `python:3.10-slim` 為基底，透過 Volume 掛載 `main.py` 與 `requirements.txt`。
*   **優點**: 環境隔離、目錄結構清晰、支援透過 FileBrowser 即時更新代碼而無需重新構建映像檔。

## 🚨 關鍵安全規則 (Critical Safety Rules)

### 1. 資料庫刪除規則
> [!DANGER]
> **嚴禁刪除任何 MSSQL 表格**
> - 來源資料庫 (APP_SRV_BPM, APP_SRV_COMMON) 為生產環境資料
> - 禁止執行 `DROP TABLE`, `DELETE FROM`, `TRUNCATE TABLE` 指令

### 2. ClickHouse 表格刪除規範
> [!WARNING]
> **刪除 ClickHouse 表格需經過三次確認**
> 如需執行 `DROP TABLE` 或 `TRUNCATE TABLE`，必須向用戶確認三次：
> 1. 第一次：說明刪除原因和受影響範圍
> 2. 第二次：確認是否有備份或可還原
> 3. 第三次：再次請求用戶明確授權「請執行刪除」
