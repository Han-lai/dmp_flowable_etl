# DML 檔案說明

## 檔案清單與用途

### Silver 層
- `backfill_pivot.sql` - Dimension Pivot (varinst 樞紐轉換)
- `backfill_silver.sql` - Silver Facts (任務事實表)
- `backfill_exclusion.sql` - Silver Exclusion (排除邏輯)

### Gold 層
- `backfill_gold_milestone.sql` - Gold Milestone 統計 (里程碑指標)
- `backfill_gold_acc.sql` - Gold Accumulation 統計 (累積指標)
- `sync_gold_unified.sql` - Gold Unified 同步 (統一表)

### 已棄用
- `backfill_gold.sql` - **已棄用** (功能已拆分為 backfill_gold_milestone.sql + backfill_gold_acc.sql + sync_gold_unified.sql)

## 執行順序

1. **Bronze → Silver**:
   - backfill_pivot.sql
   - backfill_silver.sql
   - backfill_exclusion.sql

2. **Silver → Gold**:
   - backfill_gold_milestone.sql
   - backfill_gold_acc.sql
   - sync_gold_unified.sql

## 注意事項

- 所有檔案使用 `bronze.*` 資料庫引用
- 執行由 `scripts/etl/execute_etl.py` 統一管理
- 時間範圍參數: `{start_ts}`, `{end_ts}`
