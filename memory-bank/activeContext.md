# 當前工作狀態 - DMP Flowable

## 最後更新
2026-01-30 16:12

## 當前任務
**專案檔案整理與歸檔**

## 進行中的工作

### 檔案結構重整 (2026-02-02 完成)
- **保留 Active**:
  - `sql/rebuild/` (新架構 SQL)
  - `scripts/rebuild/` (新架構腳本)
  - `docs/` (文件)
  - 核心驗證腳本: `verify_l5_queries.py`, `test_time_filter.py`, `query_gold_l5.py` 等

- **歸檔 Legacy**:
  - `scripts/etl`, `scripts/sync`, `scripts/setup`, `scripts/deploy` → `ARCHIVE/legacy_architecture/scripts/`
  - 根目錄舊腳本 → `ARCHIVE/legacy_architecture/scripts/`
  - 根目錄舊 SQL → `ARCHIVE/legacy_architecture/sql/`

- **歸檔 One-off**:
  - `scripts/validation/` 下的一次性檢查腳本 → `ARCHIVE/one_off_scripts/validation/`

## 待辦事項
- [x] 執行檔案整理腳本 (`file_organizer.py`)
- [ ] 確認 Gold 層 Refreshable MView 運行狀態 (下週)
