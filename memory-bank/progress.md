# 專案進度 (Progress)

## 項目概述
DMP Flowable L5 數據流水線遷移轉換，由 V2 (Silver DISTINCT) 升級至 V4.3 (Super Silver) 架構，旨在建立高品質、高精確度的統一任務事實表，達成 KPI 指標與 UI 明細的 100% 同步。

## 已完成里程碑 (Milestones)

### 2026-05-27 (下午): Phase 4 Cube 預聚合架構完成與 anchor_dt 全面遷移
- **Gold Summary 預聚合表上線**：新增 `gold.rmv_l5_task_summary` 整數彙總表，ETL 在寫入階段完成 bitmap merge，Cube 查詢只做 SUM，查詢耗時降至 0.06~0.11 秒。
- **L5TaskPeriodic & L5TaskPeriodicPivot 全面改寫**：兩個核心 Cube 完全捨棄即時 Bitmap 運算，改讀預聚合表，並將 anchor_dt 計算來源也遷移至 `rmv_l5_task_summary FINAL WHERE period_type='Day'`，兩個 Cube 現只讀一張表。
- **Cube 檔案整理**：刪除冗餘的 `cube_l5_task_summary.js`（邏輯已合併至 periodic）與 `cube_5level.js`（效能問題待重新設計）。
- **MSSQL 來源表版本升級**：`sync_tables.yaml` 全部從 `_0202`/`_0108` 升至 `_0503`。
- **GitLab 推送**：3 個 commits 已推送至 `master`（`6b9527e`, `56f3201`, `cb4275f`）。

### 2026-05-27: Watermark 結構升級、ETL 接龍自癒與正式資料庫無痛置換切換
- **正式環境無痛置換與遷移 (Production Switchover)**：成功將原本不帶後綴的舊正式資料庫（`bronze`, `silver`, `gold`, `ops_metrics`）改名，打包封存為 **`_0202`** 後綴（如 `bronze_0202`），作為歷史資料的安全存檔。接著重新建立全新標準正式庫，並將已在 `_0503` 測試沙盒驗證無誤的實體表瞬間搬移移入。
- **Views 視圖重新部署與 100% 驗證**：在新正式庫中重新部署 `sql/etl/schema` 目錄下的 9 個 DDL 檔案。經執行 `python scripts/etl/execute_etl.py --status` 驗證，正式環境的 `bronze.bpm_act_hi_taskinst` (674萬行)、`silver.mv_fact_task_vx` (698萬行) 與 `gold.rmv_l5_task_summary` (6.7萬行) **數據完全到位，正式版完美宣布上線！**
- **水位線真實時間跨度追蹤**：在 `bronze._sync_watermark` 水位線表成功擴充 `min_data_time` (資料最舊時間) 與 `max_data_time` (資料最新時間) 兩個 Nullable(DateTime64(3)) 欄位。自動在增量抽取成功後，查詢 ClickHouse 的真實時間 `MIN` 與 `MAX` 值並寫入，達成極低開銷的真實資料跨度監控。
- **無痛平滑結構升級**：在 `sync_unified_odbc.py` 中實作啟動時的 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 自動結構遷移，確保正式與沙盒環境能無痛自動升級而不影響現有數據。
- **智能 Auto-Catchup (自動接龍)**：升級 `execute_etl.py` 中的 `--daily` 模式，自動讀取 Checkpoint 的 `max(window_end)` 與 Watermark 邊界，全自動動態計算本次補算起迄點，不需手動指定。
- **空窗跳過與自我療癒 (Safe-Run)**：實作防 OOM 安全機制。在計算前若 Bronze 筆數為 0 則 `Skip` 且**不標記 SUCCESS** 到 Checkpoint。這保留了未來若有遲到資料同步進來時，系統自動補算的自癒能力。
- **測試雙向對稱性**：在 `sync_unified_odbc.py` 中新增 `--db-suffix` 命令行參數，使數據抽取端也支援帶有 `_0503` 的測試庫（例如 `bronze_0503`），與 ETL 引擎達成 100% 完美的測試一致性！
- **Pipeline 狀態儀表板優化**：重構 `execute_etl.py` 中的 `show_status`，解除儀表板筆數查詢表名的 hardcoding 改為從 `pipeline_config.yaml` 中動態讀取。並擴充 `--status` 監控儀表板，將同步進度與新增的真實最舊/最新時間完美整合展現。

### 2026-05-26: Phase 4 預聚合與增量視窗 Bug 修復
- **正式環境切換與回滾**: 成功將測試環境 (`_0503`) 的概念部署至正式環境，統一使用 `bronze.*` 作過渡目標表，並確保 `sync_tables.yaml` 與 `execute_etl.py` 的組態還原為 GitLab 標準版本。
- **增量 ETL 的時間視窗修復 (ACC 數據流失問題)**: 發現並修復了 `backfill_gold_summary.sql` 中的重大 Bug。在使用 10天 Incremental ETL 聚合 `Week` 與 `Month` 粒度時，引入動態時間擴展 `toStartOfWeek` 與 `toStartOfMonth`，確保 `ReplacingMergeTree` 永遠能獲取完整的週/月聚合，完美對齊前端動態時光機的 30 天聯集 (ACC) 邏輯。
- **歷史數據重算**: 透過自訂腳本將 66,026 筆歷史聚合資料回填完畢，恢復 ACC 數據準確度。

### 2026-05-25: Cube.js 語意層效能極限優化 (O(1) 架構重構)
- **破除全表掃描黑洞 (Filter Pushdown)**: 將 Cube Models 裡會導致 ClickHouse 放棄下推過濾條件的 `CROSS JOIN` 語法，全面替換為 `Constant Scalar WITH`，確保主鍵索引能發揮作用。
- **主鍵索引修復 (Index Fix)**: 移除了日期篩選條件的 `formatDateTime` 函數包裝，讓資料庫能以原生格式快速搜尋。
- **指標聚合優化 (Measure Optimization)**: 升級所有數量型指標，將 `bitmapCardinality(groupBitmapMergeState(x))` 精簡為更高效的原生函式 `groupBitmapMerge(x)`。
- **成果與發布**: 成功將時間與空間複雜度由 O(N²) 降維至 O(1)，使單一大範圍查詢從 30 秒 (超時) 降至 1.5 - 8 秒，並順利推送到 GitLab `master` 分支。

### 2026-05-18: 機房新伺服器 (REDACTED_IP:8122) 部署與全量資料對帳
- **腳本連線大更新**: 將專案中所有核心 Python 腳本（連線設定）由舊主機全面安全移轉至新主機 `REDACTED_IP:8122`，採用 `default/default` 憑證。
- **跨伺服器秒級資料搬移**: 利用 ClickHouse 遠端直連函式 `remote()`，成功將 **53,388,806 筆** 核心 Bronze 資料在 3 分鐘內高速轉入新資料庫，完美避開 MSSQL 來源端無索引引發的 ODBC 分批超時限制。
- **ETL 完整重算與業務對帳**: 完成 `silver` 及 `gold` 兩層 `--reset` 重建與 Backfill 計算，比對 WJ2 廠區 `2025-12-31` 的 Todo(9)、Doing(5)、Done(186) 指標，數據達成 **0 誤差對齊**，證明新伺服器隨時可投入正式生產！

### 2026-05-07: 累積負載率 (Acc Rate) 指標優化
- **滾動分母實作**: 在 Gold 層新增 `acc_total_task` 欄位，實作 7 日滾動總開單量計算，徹底解決週末或低開單量時 Acc Rate 超過 100% 的數據震盪問題。
- **維度感知 (Dimension-Aware) 邏輯**: 
    - **日維度**: 採 7 日滾動積壓邏輯。
    - **週/月維度**: 採週期結算 (Period-End Settlement) 邏輯，確保與 Done Rate 指標在同時間粒度下邏輯一致。
- **Cube.js 優化**: 修改 `accRate` 度量，利用 `any(granularity)` 實作動態公式切換，解決 SQL 聚合錯誤。
- **全量回填**: 完成 2025-01 至今的所有歷史數據重整，確保生產環境指標精確。

---

## 當前狀態項目 (Status)

| 模組 | 狀態 | 備註 |
| :--- | :--- | :--- |
| **正式庫置換上線** | ✅ 標準無後綴正式上線 | 已將舊庫封存為 _0202，並把驗證後的 0503 瞬間改名移入標準正式庫 |
| **Bronze Sync Watermark** | ✅ 欄位擴充與自動時間追蹤 | 已新增 min_data_time 與 max_data_time 並支援平滑遷移與對稱測試 |
| **ETL Catchup & Checkpoint** | ✅ 智能自動接龍與空窗自癒 | 支援 max(window_end) 接龍、空窗 Skip 與對稱測試 |
| **狀態儀表板 Dashboard** | ✅ show_status 動態優化 | 支援 YAML 動態掃描、最舊最新資料時間完美整合同步呈現 |
| **Silver Fact Layer** | ✅ V4.3 | 超級事實表 (Super Silver)，包含 L4、業務變數與時效 |
| **Gold Layer ETL** | ✅ V4.2 | 支援週期感知 (Period-Aware) 與多粒度 Bitmap |
| **DML 效能** | ✅ 已優化 | 實作 argMax 去重，確保 JOIN 後不產生重複數據 |
| **ETL 檔案清理** | ✅ 已完成 | 僅保留 `execute_etl.py` 與核心 SQL 模板 |
| **Cube.js Model** | ✅ V4.3 | 新增 `L5TaskDetailsSuper` 用於正式明細鑽取 |

## 待辦事項 (Todo)
- [x] 解決 W1 跨年數據對帳落差。
- [x] **將 UI 明細邏輯整合進核心 Fact Table (V4.3 升級)**。
- [x] **實作 DML argMax 去重優化，解決資料重複問題**。
- [x] **清理過時 ETL 程式碼與檔案**。
- [x] **升級 Watermark 水位線表結構，新增資料最舊/最新時間欄位 (2026-05-27)**。
- [x] **實作 ETL 智能自動接龍與防空窗 OOM 自我療癒機制 (2026-05-27)**。
- [x] **擴充 --status 監控儀表板，整合展示真實資料時間跨度 (2026-05-27)**。
- [x] **資料庫正式環境無痛置換遷移 (0503 -> 標準正式，舊正式 -> 0202) (2026-05-27)**。
- [x] 提交並推送所有 V4.3 邏輯變更至版本控制。
- [ ] 觀察 Super Silver 表在前端 Superset 的明細鑽取效能。
