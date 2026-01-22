# MView 歷史日期支援修正需求文件

## 專案背景

當前 Gold 層 MView (`DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV`) 使用 `toDate(now())` 作為快照日期，導致無法支援歷史日期查詢。此問題影響了 L5 任務完成率指標的歷史趨勢分析功能。

### 問題描述

1. **當前實作問題**：Gold 層 MView 使用 `toDate(now())` 導致所有歷史資料都顯示為當前日期
2. **業務影響**：無法進行歷史趨勢分析，特定日期的任務狀態查詢失效
3. **測試案例失敗**：WJ2+NBU+E5 2025-12-30 測試案例無法正確查詢歷史資料

### 解決方案概述

修正 Gold 層 MView 邏輯，使用 Silver 層的實際 `snapshot_date` 欄位，而非當前日期。

---

## Requirements

### Requirement 1: Gold 層 MView 歷史日期支援

**User Story:** As a 業務分析師, I want Gold 層 MView 支援歷史日期查詢, so that 我能分析 L5 任務完成率的歷史趨勢。

#### Acceptance Criteria

1. WHEN 查詢 Gold 層 MView THEN 系統 SHALL：
   - 使用 Silver 層的實際 `snapshot_date` 而非 `toDate(now())`
   - 保留每日的歷史快照資料
   - 支援任意歷史日期的資料查詢

2. WHEN 執行歷史日期查詢 THEN 系統 SHALL：
   - 正確返回指定日期的任務狀態分布
   - 計算結果與該日期的實際業務狀況一致
   - 支援日期範圍查詢（如：過去 30 天趨勢）

3. WHEN MView 更新 THEN 系統 SHALL：
   - 保持現有資料的完整性
   - 新增的資料使用正確的快照日期
   - 不影響當前的資料更新機制

---

### Requirement 2: 測試案例驗證

**User Story:** As a 資料工程師, I want 使用 WJ2+NBU+E5 2025-12-30 測試案例驗證修正結果, so that 我能確保歷史日期查詢功能正常運作。

#### Acceptance Criteria

1. WHEN 查詢 WJ2+NBU+E5 2025-12-30 THEN 系統 SHALL 返回：
   - 總任務數：7 個
   - TODO 任務：6 個
   - DOING 任務：1 個  
   - DONE 任務：0 個
   - 完成率：0.0%
   - 執行率：14.3%

2. WHEN 驗證資料一致性 THEN 系統 SHALL 確保：
   - Silver 層 → Gold 層資料一致
   - Gold 層 → Cube 層資料一致
   - 所有層級的計算結果完全相符

3. WHEN 執行端到端測試 THEN 系統 SHALL：
   - 通過 Bronze → Silver → Gold → Cube 完整資料流驗證
   - 確認歷史日期查詢在所有層級都正常運作
   - 驗證新的 MView 邏輯不影響當前日期的查詢

---

### Requirement 3: Cube.js 整合驗證

**User Story:** As a 前端開發者, I want Cube.js 能正確查詢修正後的 Gold 層資料, so that 儀表板能顯示正確的歷史趨勢。

#### Acceptance Criteria

1. WHEN Cube.js 查詢歷史資料 THEN 系統 SHALL：
   - 正確解析 `snapshotDate` 時間維度
   - 支援按日期篩選和分組
   - 返回準確的歷史指標數值

2. WHEN 執行時間序列查詢 THEN 系統 SHALL：
   - 支援日/週/月等不同時間粒度
   - 正確計算各時間區間的聚合指標
   - 提供完整的歷史資料覆蓋範圍

3. WHEN 驗證 Cube 功能 THEN 系統 SHALL：
   - L5 任務完成率 Cube 正常運作
   - 人員使用率 Cube 不受影響
   - 所有預聚合配置正確更新

---

### Requirement 4: 資料完整性保證

**User Story:** As a 系統管理員, I want 確保 MView 修正不會影響現有資料和系統穩定性, so that 業務運作不會中斷。

#### Acceptance Criteria

1. WHEN 執行 MView 修正 THEN 系統 SHALL：
   - 備份現有的 Gold 層資料
   - 使用 `POPULATE` 重新填充歷史資料
   - 驗證修正前後的資料總量一致

2. WHEN 部署修正版本 THEN 系統 SHALL：
   - 保持 MView 的自動更新機制
   - 確保 `ReplacingMergeTree` 引擎正常運作
   - 維持現有的查詢效能

3. WHEN 監控系統運作 THEN 系統 SHALL：
   - 提供修正前後的對比報告
   - 監控 MView 更新頻率和延遲
   - 確保所有相關腳本和工具正常運作

---

## 技術實作細節

### 修正前的問題邏輯
```sql
SELECT 
    toDate(now()) AS snapshot_date,  -- 問題：所有資料都是當前日期
    -- ... 其他欄位
FROM silver.mv_l5_metrics_realtime
```

### 修正後的正確邏輯
```sql
SELECT 
    snapshot_date,  -- 修正：使用 Silver 層的實際日期
    -- ... 其他欄位
FROM silver.mv_l5_metrics_realtime
GROUP BY 
    snapshot_date,  -- 修正：按實際日期分組
    -- ... 其他維度
```

### 影響範圍
- **主要檔案**：`sql/13_create_gold_mviews.sql`
- **相關 Cube**：`cube/model/cubes/cube_gold_l5_task_completion.js`
- **驗證腳本**：`scripts/verify_l5_cube_wj2_nbu_e5_2025_12_30.py`

---

## 驗收標準

### 功能驗收
- ✅ Gold 層 MView 支援歷史日期查詢
- ✅ WJ2+NBU+E5 2025-12-30 測試案例通過
- ✅ Cube.js 歷史趨勢查詢正常
- ✅ 資料一致性驗證通過

### 效能驗收
- ✅ MView 更新時間不超過現有基準的 110%
- ✅ 歷史日期查詢響應時間 < 5 秒
- ✅ 系統記憶體使用量無異常增長

### 穩定性驗收
- ✅ 連續 7 天無 MView 更新失敗
- ✅ 所有現有查詢功能正常運作
- ✅ 無資料遺失或重複

---

## 風險評估

| 風險項目 | 影響程度 | 機率 | 緩解措施 |
|---------|---------|------|---------|
| 歷史資料重新計算耗時過長 | 中 | 低 | 分批處理，監控進度 |
| MView 更新機制異常 | 高 | 低 | 完整測試，準備回滾方案 |
| Cube 查詢效能下降 | 中 | 中 | 優化預聚合配置 |
| 資料一致性問題 | 高 | 低 | 多層驗證，自動化測試 |

---

## 後續規劃

1. **Phase 1**：修正 Gold 層 MView 邏輯
2. **Phase 2**：驗證資料完整性和一致性  
3. **Phase 3**：更新相關文件和監控機制
4. **Phase 4**：建立自動化測試和告警機制