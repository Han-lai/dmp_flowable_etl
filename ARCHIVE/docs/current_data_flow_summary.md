# 目前專案實際資料流程總結

## 資料流程概覽

1. **資料來源**: MSSQL (twtpesqldv2.delta.corp:1433)
   - APP_SRV_BPM 資料庫：流程引擎資料 (ACT_HI_*)
   - APP_SRV_COMMON 資料庫：業務資料 (FlowableTaskStats, HR_Employee 等)

2. **第一張 ClickHouse Raw Table**: Bronze 層表格
   - 透過 JDBC Bridge 直接從 MSSQL 同步到 `bronze.*` 表格
   - 共 19 張表格，包含 BPM 流程資料和 Common 業務資料

3. **Bronze → Silver 轉換方式**: 
   - **主要方式**: Python 批次 ETL (`scripts/transform_silver_*.py`)
   - **新增方式**: Materialized Views 即時轉換 (`sql/11_create_silver_mviews_layer1.sql`)

4. **目前資料路徑**: 
   - **批次路徑**: Bronze → Silver (Python ETL) → Gold (聚合快照)
   - **即時路徑**: Bronze → Silver MViews → 即時查詢 (並行運行)

5. **同步機制**:
   - **大表**: 增量同步 (使用 watermark 追蹤)
   - **小表**: 全量同步 (DROP + CREATE)

6. **舊流程狀況**: 
   - 無舊的 table-based 流程，目前只有一條主要路徑
   - MViews 為新增的即時查詢能力，與批次處理並行

## 技術細節

- **同步工具**: `sync/sync_incremental.py` (主要) + `sync/sync_to_clickhouse.py` (備用)
- **轉換引擎**: ClickHouse ReplacingMergeTree + Python ETL
- **資料新鮮度**: Bronze (即時) → Silver (批次/即時) → Gold (每日快照)
- **查詢介面**: 批次表 + MViews 雙軌並行