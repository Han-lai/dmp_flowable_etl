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
    │ Silver  │  清洗轉換層 (Refreshable MView + Physical Fact)
    │ 層      │  - mv_varinst_pivoted (變數透視)
    │         │  - mv_fact_task_vx (核心物理事實表)
    └────┬────┘  
         │       
    ┌────┴────┐
    │ Gold    │  指標聚合層 (Physical Snapshot Tables)
    │ 層      │  - gold.rmv_l5_task_completion_phys (L5 實體表)
    │         │  - gold.rmv_l5_acc_phys (ACC 實體表)
    └────┬────┘  
         │
    ┌─────────┐
    │ Cube.js │  語意層 API (與 Superset 整合)
    └─────────┘
          │
    ┌─────────┐
    │ FastAPI │  進階報表 API (自定義複雜格式)
    └─────────┘
```

## 關鍵技術決策

### 1. VTYPE 分類邏輯 (2026-04-15 更新 - 簡化版)
- **規則優先順序**:
    1. 規則 1: 特定工單號 → V1
    2. 規則 2-4: TASK_DEF_KEY_ 前綴匹配 (V1%, V2%, V3%)
    3. 規則 5: 預設
- **工單號列表**: '196','199','200','210','212','213'
- **變更說明**:
    - 移除舊規則 1 (DG3 + 工單號) - 冗餘
    - 移除舊規則 2 (NPE + 工單號) - 冗餘
    - 保留規則 3 (僅工單號) 並重新編號為規則 1
- **實作位置**: `sql/etl/dml/backfill_silver.sql`

### 2. 為什麼從 JDBC 遷移至 Native ODBC？ (2026-03-27)
- **穩定性**: 解決 JDBC-bridge 頻繁發生的 Java Heap Space OOM 問題。
- **效能**: 使用 `msodbcsql18` 原生驅動，降低資料轉換開銷。
- **解耦**: 移除對 Java 環境的依賴，簡化 Docker 容器架構。

### 3. ODBC 死鎖 (Deadlock) 繞過方案
- **問題**: `odbc()` 表函數在讀取主檔 (如 `hr_employee`) 時，會因 MS-ODBC 動態探測 Schema 導致卡死。
- **解法**: 使用 `CREATE TABLE ... ENGINE = ODBC` 硬性定義 DDL，阻止驅動執行耗時的 Metadata 探測。

### 4. 計算架構 (Windowed Computation)
- **實作**: 透過 `bronze.etl_checkpoint` 記錄每個運算時間視窗的狀態。
- **10-Day Windowing**: 針對 Server 76 的 6GB RAM 限制，將補分運算切分為 10 日一組的滾動視窗，確保長週期 (15個月) 運算不崩潰。
- **低記憶體模式 (--low-ram)**: 被動限制 ClickHouse 執行緒與啟用磁碟溢出 (Spill to disk)，優先保證系統穩定性。
- **斷點續傳**: 程式失敗後自動從最後一個成功的 Checkpoint 續跑。

### 5. 重複資料處理 (ReplacingMergeTree)
- 使用 `ReplacingMergeTree(_sync_version)`。
- **優點**: 支援分批次 (Batch) 寫入相同的主鍵，並自動保留最新版本，消滅 DELETE 性能負擔。
 
### 6. 指標計算與對齊模式 (Metric & Parity Patterns)
- **Any-Event Filter**: 納入所有在 `ACT_HI_TASKINST` 中有活動記錄的關聯事件以對齊 Baseline。
- **180 天變數回溯**: 確保長週期任務的維度 (Region/Plant) 不缺失。
- **金層實體表與視圖 (Gold 2-Tier Architecture)**: 
    - `gold.rmv_l5_task_completion_phys`: 實體表，儲存冪等快照。
    - `gold.rmv_l5_task_completion`: 視圖層，提供給 Cube.js，實現讀寫隔離。
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
