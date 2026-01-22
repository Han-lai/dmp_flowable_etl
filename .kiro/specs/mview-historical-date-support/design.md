# MView 歷史日期支援設計文件

## 設計概述

本設計文件詳細說明如何修正 Gold 層 MView 的歷史日期支援問題，確保 L5 任務完成率指標能正確進行歷史趨勢分析。

## 問題分析

### 根本原因
Gold 層 MView (`DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV`) 在建立時使用了 `toDate(now())` 作為 `snapshot_date`，導致：

1. **時間維度錯誤**：所有歷史資料都被標記為當前日期
2. **資料覆蓋問題**：每次 MView 更新都會覆蓋之前的快照
3. **查詢失效**：無法按歷史日期篩選和分析資料

### 資料流影響
```
Silver Layer (正確) → Gold Layer (錯誤) → Cube Layer (受影響)
     ↓                    ↓                    ↓
snapshot_date        toDate(now())      snapshotDate 維度失效
```

## 技術設計

### 1. MView 結構修正

#### 修正前的錯誤邏輯
```sql
CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
ENGINE = ReplacingMergeTree()
ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
AS
SELECT 
    toDate(now()) AS snapshot_date,  -- ❌ 問題：固定為當前日期
    COALESCE(plant, '') AS plant,
    -- ... 其他欄位
FROM silver.mv_l5_metrics_realtime
GROUP BY 
    toDate(now()),  -- ❌ 問題：按當前日期分組
    plant, factory, line, vx_type, vx_subtype
```

#### 修正後的正確邏輯
```sql
CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
ENGINE = ReplacingMergeTree()
ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
SETTINGS allow_nullable_key = 1
POPULATE  -- ✅ 重新填充歷史資料
AS
SELECT 
    snapshot_date,  -- ✅ 修正：使用 Silver 層的實際日期
    COALESCE(plant, '') AS plant,
    -- ... 其他欄位
FROM silver.mv_l5_metrics_realtime
GROUP BY 
    snapshot_date,  -- ✅ 修正：按實際日期分組
    plant, factory, line, vx_type, vx_subtype
```

### 2. 資料重建策略

#### Step 1: 備份現有資料
```sql
-- 建立備份表
CREATE TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV_BACKUP
ENGINE = MergeTree()
ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
AS SELECT * FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;
```

#### Step 2: 重建 MView
```sql
-- 刪除舊 MView
DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;

-- 建立新 MView（使用修正後的邏輯）
CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
-- ... 修正後的完整定義
```

#### Step 3: 驗證資料完整性
```sql
-- 檢查資料覆蓋範圍
SELECT 
    MIN(snapshot_date) AS earliest_date,
    MAX(snapshot_date) AS latest_date,
    COUNT(DISTINCT snapshot_date) AS date_count,
    COUNT(*) AS total_rows
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;

-- 驗證特定測試案例
SELECT * FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
WHERE snapshot_date = '2025-12-30'
  AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5';
```

### 3. Cube.js 整合調整

#### 時間維度配置
```javascript
// cube/model/cubes/cube_gold_l5_task_completion.js
dimensions: {
  snapshotDate: {
    type: `time`,
    sql: `snapshot_date`,  // ✅ 確保使用正確的欄位
    title: '快照日期',
    description: 'L5 指標快照日期',
  },
  // ... 其他維度
}
```

#### 預聚合配置更新
```javascript
preAggregations: {
  dailyVxSummary: {
    measures: [/* ... */],
    dimensions: [
      GoldL5TaskCompletion.snapshotDate,  // ✅ 時間維度
      // ... 其他維度
    ],
    timeDimension: GoldL5TaskCompletion.snapshotDate,
    granularity: `day`,
    refreshKey: {
      every: `1 hour`,
    },
  },
}
```

### 4. 查詢視圖更新

#### 業務友好視圖
```sql
-- 更新查詢視圖以支援歷史日期
CREATE OR REPLACE VIEW gold.vw_daily_l5_completion_summary AS
SELECT 
    snapshot_date,  -- ✅ 正確的歷史日期
    plant, factory, line, vx_type, vx_subtype,
    sum_total_task_qty AS total_tasks,
    -- ... 其他欄位
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
ORDER BY snapshot_date DESC, plant, factory, line, vx_type, vx_subtype;
```

#### 歷史趨勢分析視圖
```sql
-- 新增歷史趨勢分析視圖
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

## 效能考量

### 1. 儲存空間影響

#### 修正前（錯誤）
- 每次更新覆蓋前一天資料
- 儲存空間：~1 天份資料

#### 修正後（正確）
- 保留所有歷史快照
- 儲存空間：~N 天份資料（N = 資料保留天數）

#### 空間估算
```sql
-- 估算每日資料量
SELECT 
    COUNT(*) AS daily_rows,
    COUNT(*) * 365 AS yearly_rows_estimate
FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
WHERE snapshot_date = today();
```

### 2. 查詢效能優化

#### 索引策略
```sql
-- 主要排序鍵（已包含在 ORDER BY 中）
ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)

-- 額外索引（如需要）
ALTER TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV 
ADD INDEX idx_snapshot_vx (snapshot_date, vx_type) TYPE minmax GRANULARITY 1;
```

#### 分區策略（可選）
```sql
-- 按月分區（如資料量很大）
ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
```

### 3. MView 更新機制

#### 增量更新邏輯
```sql
-- MView 會自動處理增量更新
-- 當 Silver 層有新資料時，Gold 層會自動更新對應的 snapshot_date 分區
```

#### 更新頻率控制
```sql
-- 可以通過 Silver 層的更新頻率來控制 Gold 層更新
-- 建議：Silver 層每小時更新，Gold 層自動跟隨
```

## 測試策略

### 1. 單元測試

#### 資料完整性測試
```python
def test_historical_date_coverage():
    """測試歷史日期覆蓋範圍"""
    query = """
    SELECT COUNT(DISTINCT snapshot_date) as date_count
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
    WHERE snapshot_date >= '2025-12-01'
    """
    result = execute_query(query)
    assert result[0]['date_count'] > 20  # 至少 20 天的資料

def test_wj2_nbu_e5_case():
    """測試 WJ2+NBU+E5 2025-12-30 案例"""
    query = """
    SELECT sum_total_task_qty, sum_done_qty, completion_rate
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
    WHERE snapshot_date = '2025-12-30'
      AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    """
    result = execute_query(query)
    assert result[0]['sum_total_task_qty'] == 7
    assert result[0]['sum_done_qty'] == 0
    assert result[0]['completion_rate'] == 0.0
```

#### 資料一致性測試
```python
def test_silver_gold_consistency():
    """測試 Silver 和 Gold 層資料一致性"""
    # 比較 Silver 和 Gold 層的聚合結果
    silver_query = """
    SELECT snapshot_date, SUM(total_task_qty) as total
    FROM silver.mv_l5_metrics_realtime
    WHERE snapshot_date = '2025-12-30'
    GROUP BY snapshot_date
    """
    
    gold_query = """
    SELECT snapshot_date, SUM(sum_total_task_qty) as total
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
    WHERE snapshot_date = '2025-12-30'
    GROUP BY snapshot_date
    """
    
    silver_result = execute_query(silver_query)
    gold_result = execute_query(gold_query)
    
    assert silver_result[0]['total'] == gold_result[0]['total']
```

### 2. 整合測試

#### Cube.js 查詢測試
```javascript
// 測試 Cube.js 歷史日期查詢
const query = {
  measures: ['GoldL5TaskCompletion.totalTasks'],
  timeDimensions: [{
    dimension: 'GoldL5TaskCompletion.snapshotDate',
    dateRange: ['2025-12-28', '2025-12-30'],
    granularity: 'day'
  }],
  filters: [
    { member: 'GoldL5TaskCompletion.plant', operator: 'equals', values: ['WJ2'] }
  ]
};

// 驗證查詢結果包含正確的歷史資料
```

### 3. 效能測試

#### 查詢響應時間測試
```python
def test_query_performance():
    """測試歷史日期查詢效能"""
    import time
    
    query = """
    SELECT * FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
    WHERE snapshot_date BETWEEN '2025-12-01' AND '2025-12-31'
    """
    
    start_time = time.time()
    result = execute_query(query)
    end_time = time.time()
    
    query_time = end_time - start_time
    assert query_time < 5.0  # 查詢時間應小於 5 秒
```

## 部署計畫

### Phase 1: 準備階段
1. 備份現有 Gold 層資料
2. 準備修正後的 SQL 腳本
3. 建立驗證測試腳本

### Phase 2: 執行階段
1. 執行 MView 重建
2. 驗證資料完整性
3. 更新相關查詢視圖

### Phase 3: 驗證階段
1. 執行完整測試套件
2. 驗證 Cube.js 功能
3. 確認效能指標

### Phase 4: 監控階段
1. 監控 MView 更新狀況
2. 追蹤查詢效能
3. 建立告警機制

## 回滾計畫

### 緊急回滾步驟
```sql
-- 1. 停用新 MView
DROP TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;

-- 2. 恢復備份資料
CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
ENGINE = ReplacingMergeTree()
ORDER BY (snapshot_date, plant, factory, line, vx_type, vx_subtype)
AS SELECT * FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV_BACKUP;

-- 3. 驗證回滾成功
SELECT COUNT(*) FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;
```

### 回滾觸發條件
- 資料完整性驗證失敗
- 查詢效能嚴重下降（>200% 基準時間）
- Cube.js 功能異常
- MView 更新機制失效

## 監控指標

### 資料品質指標
- 每日快照資料完整性
- Silver-Gold 層資料一致性
- 歷史日期覆蓋範圍

### 效能指標
- MView 更新延遲時間
- 歷史日期查詢響應時間
- 儲存空間使用量

### 業務指標
- L5 任務完成率計算準確性
- 歷史趨勢分析可用性
- Cube.js 查詢成功率