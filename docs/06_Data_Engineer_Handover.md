# DMP Flowable V4.3 ETL 核心維運與測試交接文件

**版本**: V4.3 (Production Ready)  
**最後更新**: 2026-05-04  
**維護者**: AIT / Data Engineering

---

## 1. 系統架構簡述 (Architecture Overview)

本專案採用 **Medallion (Bronze → Silver → Gold)** 架構，並針對 ClickHouse 25.8 進行了深度優化：

- **Bronze (Raw)**: 透過 ODBC 增量抽取 MSSQL 資料，使用 `ReplacingMergeTree` 處理更新。
- **Silver (Fact)**: 實作 **Super Silver** 邏輯，將任務狀態、業務變數與製造五階維度進行大統一聚合。
- **Gold (Agg)**: 採用 **Bitmap (groupBitmap)** 技術存儲指標（Todo/Doing/Done），支援秒級跨維度查詢。

## 2. 核心技術機制 (Core Mechanisms)

### 2.1 記憶體安全管線 (Memory-Safe Pipeline)
針對大數據量可能導致的 OOM (Code: 241) 問題，`execute_etl.py` 實作了以下保護：
- **自適應視窗切分 (Auto-Split)**: 當偵測到記憶體不足時，程式會自動將時間視窗「切半遞迴」執行，直到資料量可被安全處理。
- **外存溢流 (Spill to Disk)**: 強制設定 `max_bytes_before_external_group_by`，在記憶體達到臨界點前將中間結果寫入磁碟。

### 2.2 跨年邊界對齊 (Year-End Alignment)
- 採用 **ISO Week 與 Calendar Year 雙軌年份** 設計。
- 透過 `status_weekly` 與 `status_monthly` 獨立 Bitmap，解決了 W1 (12/29~01/04) 數據被年份切斷的問題。

---

## 3. 自動化測試防護網 (Testing Framework)

本版本導入了完整的自動化測試，確保未來任何邏輯更動都不會導致系統崩緯。

### 3.1 單元測試 (Unit Tests) - `pytest tests/`
- **Windowing**: 驗證時間視窗生成邏輯，確保無重疊、無遺漏。
- **OOM Protection**: 模擬記憶體溢位，驗證 `run_safe` 的切分與恢復能力。
- **ODBC Batching**: 驗證 MSSQL 抽取的批次切割與 23:59:59 邊界鎖定。
- **API Validation**: 驗證 L5 Insight API 的輸入參數防呆與跨年日期計算。

### 3.2 資料品質驗證 (Functional Tests) - `scratch/functional_test_suite.py`
- **狀態互斥性**: 驗證 `Total = Todo + Doing + Done`。
- **排除規則**: 驗證 `SYSTEM` 帳號與無效工單是否正確被過濾。

---

## 4. 維運操作指南 (Maintenance Guide)

### 4.1 執行全量/增量補分
```powershell
# 執行特定區段補分 (自動視窗切分)
python scripts/etl/execute_etl.py --backfill --start 2025-12-25 --end 2026-01-05

# 執行重置 (清除 Checkpoints 與目標表)
python scripts/etl/execute_etl.py --backfill --reset
```

### 4.2 執行自動化測試
```powershell
$env:PYTHONPATH='.'
pytest tests/ -v
```

---

**備註**: 本文件與 `tests/` 目錄應隨程式碼一同 Commit 至版本庫，作為 CI/CD 的檢核基準。
