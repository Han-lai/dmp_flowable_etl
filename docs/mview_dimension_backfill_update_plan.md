# MView 維度補齊更新計劃

## 📋 現況分析

### 目前架構狀況

1. **Silver Layer**
   - ✅ `silver.mv_fact_task_vx_attribution_mdm`: 已存在，57,627 rows
   - ✅ 已有 `dimension_source` 欄位
   - ❌ 缺少個別維度的資料來源追蹤 (`region_source`, `plant_source`, `factory_source`, `line_source`)
   - ❌ 未實作 VARINST 優先，MDM 補齊邏輯

2. **Gold Layer**
   - ✅ `gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT`: 已存在，3,391 rows
   - ✅ `gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV`: 已存在，1,821 rows
   - ❌ 缺少標準化的 L5 儀表板摘要表

### 維度補齊邏輯需求

根據驗證結果，需要實作：
- **VARINST 優先原則**: 有值就保持 VARINST 值
- **MDM 補齊原則**: 僅補齊缺失的維度 (主要是 region)
- **資料來源追蹤**: 每個維度標記來源 (VARINST/MDM)

## 🔄 更新計劃

### 階段 1: Silver Layer 更新

#### 1.1 更新 `silver.mv_fact_task_vx_attribution_mdm`

**目標**: 實作完整的維度補齊邏輯

**需要新增的欄位**:
```sql
region_source String,      -- 'VARINST' 或 'MDM'
plant_source String,       -- 'VARINST' 或 'MDM'  
factory_source String,     -- 'VARINST' 或 'MDM'
line_source String,        -- 'VARINST' 或 'MDM'
region String              -- 最終 region 值 (目前只有 region_code)
```

**補齊邏輯**:
```sql
-- Region 補齊 (主要需求)
COALESCE(varinst_region, mdm_region_code) AS region,
CASE 
    WHEN varinst_region IS NOT NULL THEN 'VARINST'
    WHEN mdm_region_code IS NOT NULL THEN 'MDM'
    ELSE 'MISSING'
END AS region_source,

-- Plant 補齊 (保持 VARINST 優先)
COALESCE(varinst_plant, mdm_plant_code) AS plant,
CASE 
    WHEN varinst_plant IS NOT NULL THEN 'VARINST'
    WHEN mdm_plant_code IS NOT NULL THEN 'MDM'
    ELSE 'MISSING'
END AS plant_source,

-- Factory 補齊 (保持 VARINST 優先)
COALESCE(varinst_factory, mdm_factory_code) AS factory,
CASE 
    WHEN varinst_factory IS NOT NULL THEN 'VARINST'
    WHEN mdm_factory_code IS NOT NULL THEN 'MDM'
    ELSE 'MISSING'
END AS factory_source,

-- LineName 補齊 (通常不需要，但保持一致性)
COALESCE(varinst_line, mdm_line_name) AS line_name,
CASE 
    WHEN varinst_line IS NOT NULL THEN 'VARINST'
    WHEN mdm_line_name IS NOT NULL THEN 'MDM'
    ELSE 'MISSING'
END AS line_source
```

**實作步驟**:
1. 備份現有 mview
2. 修改 mview 定義，加入維度補齊邏輯
3. 重建 mview
4. 驗證資料正確性

### 階段 2: Gold Layer 更新

#### 2.1 更新 `gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT`

**目標**: 使用 Silver 層的補齊結果

**需要修改**:
- 使用 Silver 層的 `region`, `plant`, `factory`, `line_name` 欄位
- 保留資料來源追蹤資訊
- 確保維度完整性

#### 2.2 建立標準化儀表板表

**建立**: `gold.l5_dashboard_summary`

**用途**: 
- Superset 儀表板專用
- 包含完整的五階維度
- 包含資料來源追蹤
- 優化查詢效能

### 階段 3: 驗證與測試

#### 3.1 資料完整性驗證
- 檢查 region 補齊比例
- 驗證 VARINST 優先邏輯
- 確認資料來源標記正確

#### 3.2 效能測試
- 查詢效能比較
- mview 重建時間
- 儲存空間使用

#### 3.3 業務邏輯驗證
- 使用測試樣本驗證
- 與既有報表比對
- Superset 儀表板測試

## 📊 預期效果

### 資料品質提升
- Region 維度完整性: 從 ~60% 提升到 ~95%
- 維度一致性: 統一的補齊邏輯
- 資料來源透明: 明確標記每個維度來源

### 業務價值
- 完整的五階維度分析
- 準確的區域統計
- 可追蹤的資料品質

### 技術改進
- 標準化的維度補齊邏輯
- 可重用的 MDM 整合模式
- 清晰的資料血緣關係

## 🚀 實作優先順序

### 高優先級 (立即執行)
1. **Silver Layer**: `silver.mv_fact_task_vx_attribution_mdm` 更新
   - 影響範圍最大
   - 其他表依賴此表
   - 核心業務邏輯

### 中優先級 (後續執行)
2. **Gold Layer**: `gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT` 更新
   - 依賴 Silver 層完成
   - 影響儀表板顯示

3. **新建表**: `gold.l5_dashboard_summary`
   - 優化儀表板效能
   - 標準化介面

### 低優先級 (可選)
4. **其他相關表**: 根據需要逐步更新
   - 歷史資料遷移
   - 備份表清理

## ⚠️ 風險與注意事項

### 資料風險
- mview 重建期間資料不可用
- 歷史資料一致性
- 維度語意變更影響

### 技術風險
- mview 重建時間較長
- 依賴表連鎖影響
- 查詢效能變化

### 緩解措施
- 分階段執行，降低影響範圍
- 充分測試驗證
- 保留回滾方案
- 監控系統效能

---

**更新時間**: 2026-01-26  
**負責人**: DMP Team  
**預計完成**: 2026-01-27