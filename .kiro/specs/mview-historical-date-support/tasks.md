# MView 歷史日期支援任務清單

## 任務概述

本任務清單詳細列出修正 Gold 層 MView 歷史日期支援所需的具體執行步驟，確保每個環節都能正確完成。

---

## Phase 1: 準備階段

### Task 1.1: 現狀分析和備份
- [ ] **1.1.1** 分析當前 Gold 層 MView 的資料分布
  ```sql
  SELECT 
      MIN(snapshot_date) AS earliest_date,
      MAX(snapshot_date) AS latest_date,
      COUNT(DISTINCT snapshot_date) AS unique_dates,
      COUNT(*) AS total_rows
  FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;
  ```
  
- [ ] **1.1.2** 備份現有 Gold 層資料
  ```sql
  CREATE TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV_BACKUP_20260122
  ENGINE = MergeTree()
  ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
  AS SELECT * FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;
  ```

- [ ] **1.1.3** 驗證 Silver 層資料的歷史覆蓋範圍
  ```sql
  SELECT 
      MIN(snapshot_date) AS earliest_date,
      MAX(snapshot_date) AS latest_date,
      COUNT(DISTINCT snapshot_date) AS date_count
  FROM silver.mv_l5_metrics_realtime;
  ```

### Task 1.2: 測試腳本準備
- [ ] **1.2.1** 建立資料完整性驗證腳本
  - 檔案：`scripts/validate_mview_historical_fix.py`
  - 功能：比較修正前後的資料一致性

- [ ] **1.2.2** 建立 WJ2+NBU+E5 測試案例腳本
  - 檔案：`scripts/test_wj2_nbu_e5_historical.py`
  - 功能：驗證特定測試案例的正確性

- [ ] **1.2.3** 建立效能基準測試腳本
  - 檔案：`scripts/benchmark_mview_performance.py`
  - 功能：測量修正前後的查詢效能

---

## Phase 2: 執行階段

### Task 2.1: MView 結構修正
- [ ] **2.1.1** 更新 `sql/13_create_gold_mviews.sql`
  - 修正 `snapshot_date` 邏輯：從 `toDate(now())` 改為使用 Silver 層的實際日期
  - 修正 GROUP BY 子句：按實際日期分組
  - 新增 `POPULATE` 關鍵字重新填充歷史資料

- [ ] **2.1.2** 執行 MView 重建
  ```bash
  # 1. 刪除舊 MView
  clickhouse-client --query "DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV"
  
  # 2. 執行修正後的 SQL
  clickhouse-client < sql/13_create_gold_mviews.sql
  ```

- [ ] **2.1.3** 驗證 MView 重建成功
  ```sql
  -- 檢查資料量和日期分布
  SELECT 
      COUNT(*) AS total_rows,
      COUNT(DISTINCT snapshot_date) AS date_count,
      MIN(snapshot_date) AS earliest,
      MAX(snapshot_date) AS latest
  FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;
  ```

### Task 2.2: 查詢視圖更新
- [ ] **2.2.1** 更新業務查詢視圖
  - 確認 `gold.vw_daily_l5_completion_summary` 使用正確的 snapshot_date
  - 更新其他相關視圖的時間邏輯

- [ ] **2.2.2** 建立歷史趨勢分析視圖
  ```sql
  CREATE VIEW gold.vw_l5_historical_trends AS
  SELECT 
      snapshot_date,
      vx_type,
      SUM(sum_total_task_qty) AS total_tasks,
      SUM(sum_done_qty) AS done_tasks,
      ROUND(SUM(sum_done_qty) * 100.0 / SUM(sum_total_task_qty), 2) AS completion_rate
  FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
  GROUP BY snapshot_date, vx_type
  ORDER BY snapshot_date DESC, vx_type;
  ```

---

## Phase 3: 驗證階段

### Task 3.1: 資料完整性驗證
- [ ] **3.1.1** 執行 WJ2+NBU+E5 2025-12-30 測試案例
  ```python
  # 執行測試腳本
  python scripts/verify_l5_cube_wj2_nbu_e5_2025_12_30.py
  
  # 預期結果：
  # - 總任務數：7
  # - TODO：6, DOING：1, DONE：0
  # - 完成率：0.0%, 執行率：14.3%
  ```

- [ ] **3.1.2** 驗證 Silver-Gold 層資料一致性
  ```python
  # 執行一致性驗證
  python scripts/verify_silver_gold_consistency_simple.py
  
  # 確認所有日期的聚合結果一致
  ```

- [ ] **3.1.3** 檢查歷史日期覆蓋範圍
  ```sql
  -- 確認至少有 30 天的歷史資料
  SELECT COUNT(DISTINCT snapshot_date) AS date_count
  FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
  WHERE snapshot_date >= today() - INTERVAL 30 DAY;
  ```

### Task 3.2: Cube.js 整合測試
- [ ] **3.2.1** 驗證 L5 任務完成率 Cube 功能
  ```javascript
  // 測試歷史日期查詢
  const query = {
    measures: ['GoldL5TaskCompletion.totalTasks', 'GoldL5TaskCompletion.completionRate'],
    timeDimensions: [{
      dimension: 'GoldL5TaskCompletion.snapshotDate',
      dateRange: ['2025-12-28', '2025-12-30'],
      granularity: 'day'
    }]
  };
  ```

- [ ] **3.2.2** 測試時間序列查詢
  ```javascript
  // 測試過去 7 天趨勢
  const trendQuery = {
    measures: ['GoldL5TaskCompletion.completionRate'],
    timeDimensions: [{
      dimension: 'GoldL5TaskCompletion.snapshotDate',
      dateRange: 'last 7 days',
      granularity: 'day'
    }],
    dimensions: ['GoldL5TaskCompletion.vxType']
  };
  ```

- [ ] **3.2.3** 驗證預聚合配置
  - 確認 `dailyVxSummary` 預聚合正常運作
  - 測試不同時間粒度的查詢效能

### Task 3.3: 效能測試
- [ ] **3.3.1** 測量歷史日期查詢效能
  ```python
  # 執行效能基準測試
  python scripts/benchmark_mview_performance.py
  
  # 確認查詢時間 < 5 秒
  ```

- [ ] **3.3.2** 監控 MView 更新時間
  ```sql
  -- 檢查 MView 最後更新時間
  SELECT MAX(_mview_update_time) AS last_update
  FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;
  ```

- [ ] **3.3.3** 評估儲存空間使用
  ```sql
  -- 檢查表大小
  SELECT 
      formatReadableSize(sum(bytes)) AS size,
      sum(rows) AS rows
  FROM system.parts 
  WHERE table = 'DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV';
  ```

---

## Phase 4: 部署和監控

### Task 4.1: 生產環境部署
- [ ] **4.1.1** 在生產環境執行相同的修正步驟
  - 按照 Phase 2 的步驟執行
  - 確保備份和回滾計畫就緒

- [ ] **4.1.2** 更新相關文件
  - 更新 `docs/silver_mviews_architecture.md`
  - 更新操作手冊和故障排除指南

- [ ] **4.1.3** 通知相關團隊
  - 通知前端團隊 Cube.js 功能更新
  - 通知業務團隊歷史趨勢分析功能可用

### Task 4.2: 監控機制建立
- [ ] **4.2.1** 建立資料品質監控
  ```python
  # 建立每日資料品質檢查腳本
  # scripts/daily_mview_quality_check.py
  
  # 監控項目：
  # - 每日快照資料完整性
  # - Silver-Gold 層一致性
  # - 歷史日期覆蓋範圍
  ```

- [ ] **4.2.2** 建立效能監控
  ```python
  # 建立效能監控腳本
  # scripts/mview_performance_monitor.py
  
  # 監控項目：
  # - MView 更新延遲
  # - 查詢響應時間
  # - 儲存空間使用
  ```

- [ ] **4.2.3** 設定告警機制
  - MView 更新失敗告警
  - 資料一致性異常告警
  - 查詢效能下降告警

### Task 4.3: 清理和優化
- [ ] **4.3.1** 清理備份資料（30 天後）
  ```sql
  -- 30 天後執行
  DROP TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV_BACKUP_20260122;
  ```

- [ ] **4.3.2** 優化查詢效能（如需要）
  - 分析查詢模式
  - 調整預聚合配置
  - 考慮新增索引

- [ ] **4.3.3** 建立自動化測試
  - 將驗證腳本加入 CI/CD 流程
  - 建立回歸測試套件

---

## 驗收標準檢查清單

### 功能驗收
- [ ] ✅ Gold 層 MView 支援歷史日期查詢
- [ ] ✅ WJ2+NBU+E5 2025-12-30 測試案例通過
- [ ] ✅ 歷史日期範圍查詢正常（如：過去 30 天）
- [ ] ✅ Cube.js 時間維度查詢正常
- [ ] ✅ 所有查詢視圖正常運作

### 資料品質驗收
- [ ] ✅ Silver-Gold 層資料完全一致
- [ ] ✅ 歷史資料無遺失或重複
- [ ] ✅ 時間序列資料連續性正常
- [ ] ✅ 聚合計算結果準確

### 效能驗收
- [ ] ✅ 歷史日期查詢響應時間 < 5 秒
- [ ] ✅ MView 更新時間不超過基準的 110%
- [ ] ✅ 儲存空間使用在合理範圍內
- [ ] ✅ Cube.js 預聚合正常運作

### 穩定性驗收
- [ ] ✅ MView 自動更新機制正常
- [ ] ✅ 連續 7 天無更新失敗
- [ ] ✅ 所有現有功能不受影響
- [ ] ✅ 回滾機制測試通過

---

## 風險緩解措施

### 高風險項目
1. **MView 重建失敗**
   - 緩解：完整備份 + 詳細測試
   - 回滾：使用備份資料快速恢復

2. **歷史資料遺失**
   - 緩解：多重驗證 + 分階段執行
   - 回滾：從 Silver 層重新生成

3. **查詢效能下降**
   - 緩解：效能基準測試 + 索引優化
   - 回滾：調整預聚合配置

### 中風險項目
1. **Cube.js 功能異常**
   - 緩解：完整整合測試
   - 回滾：更新 Cube 配置

2. **儲存空間不足**
   - 緩解：空間使用評估 + 清理策略
   - 回滾：資料分區或壓縮

---

## 完成時間估算

| Phase | 預估時間 | 關鍵路徑 |
|-------|---------|---------|
| Phase 1: 準備階段 | 4 小時 | 備份和測試腳本準備 |
| Phase 2: 執行階段 | 6 小時 | MView 重建和資料填充 |
| Phase 3: 驗證階段 | 8 小時 | 完整測試和驗證 |
| Phase 4: 部署監控 | 4 小時 | 生產部署和監控設定 |
| **總計** | **22 小時** | **約 3 個工作日** |

---

## 後續維護任務

### 短期（1-2 週）
- [ ] 監控 MView 更新穩定性
- [ ] 收集使用者回饋
- [ ] 優化查詢效能

### 中期（1-3 個月）
- [ ] 建立自動化測試
- [ ] 完善監控告警
- [ ] 文件和培訓更新

### 長期（3-6 個月）
- [ ] 評估資料保留策略
- [ ] 考慮進一步效能優化
- [ ] 規劃下一階段功能增強