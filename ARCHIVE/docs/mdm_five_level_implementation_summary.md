# MDM 五階維度實施總結

**實施日期：** 2026-01-21  
**狀態：** ✅ 完成

---

## 📋 實施內容

### 目標
將 Silver 層的五階維度從原本由 Flowable 提供的結構，改為使用 MDM 主檔表提供。

### 五階維度結構
```
V1 (業務邏輯) → Region(MFG_SITE) → Factory → Plant → Line
```

### 具體範例
```
V1 → CNE(MFG_SITE) → WJ2(Factory) → PF(Plant) → E5(Line)
```

---

## 🔄 變更內容

### 原始結構（Flowable 驅動）
```sql
-- Region 來自 FACTORY_AREA_MASTER.REGION
fa.REGION as region_code
```

### 新結構（MDM 驅動）
```sql
-- Region 現在來自 FACTORY_AREA_MASTER.MFG_SITE
fa.MFG_SITE as region_code
COALESCE(ms.MFG_SITE_DESC, fa.MFG_SITE) as region_name
```

---

## 📊 使用的 MDM 表

### 🟢 核心必需表（4張）

| 表名 | 用途 | 關鍵欄位 |
|------|------|----------|
| **MDM_LINE_DESC_MASTER** | Line 層級 | LINE_NAME, PROD_AREA_ID |
| **MDM_PROD_AREA_MASTER** | ProdArea → Factory | PROD_AREA_ID, FACTORY |
| **MDM_FACTORY_AREA_MASTER** | Factory → Region(MFG_SITE) | FACTORY, MFG_SITE |
| **MDM_MFG_PLANT_MASTER** | Plant → Factory | MFG_PLANT_CODE, FACTORY |

### 🟡 可選增強表（1張）

| 表名 | 用途 | 關鍵欄位 |
|------|------|----------|
| **MDM_MFG_SITE_MASTER** | Region 描述名稱 | MFG_SITE, MFG_SITE_DESC |

---

## 📈 實施結果

### 資料品質統計
- **總線數**: 9,492 條
- **有效線數**: 9,010 條
- **有效率**: 94.92%
- **缺失線數**: 482 條 (5.08%)

### Region 分布（Top 10）
| Region | 線數 | Factory 數 |
|--------|------|-----------|
| DG | 4,092 | 6 |
| CZ | 1,654 | 1 |
| WJ | 1,487 | 12 |
| BPO | 548 | 14 |
| WG | 519 | 3 |
| PJ | 201 | 3 |
| KG | 109 | 3 |
| TN | 107 | 1 |
| CL | 89 | 2 |
| TY | 83 | 4 |

### WJ2 Factory 的五階組合
```
WJ (Region) → WJ2 (Factory) → PF (Plant) → 112 條線
```

---

## 🔗 串接路徑

### SQL 邏輯
```sql
LINE_DESC_MASTER
    ↓ (PROD_AREA_ID)
PROD_AREA_MASTER
    ↓ (FACTORY)
FACTORY_AREA_MASTER
    ↓ (MFG_SITE)
MFG_SITE_MASTER (可選)
    ↓
五階維度完成
```

### 完整 SQL 範例
```sql
SELECT 
    -- V1 層級 (業務邏輯)
    'V1' as vx_code,
    
    -- Region 層級 (由 MFG_SITE 提供)
    fa.MFG_SITE as region_code,
    COALESCE(ms.MFG_SITE_DESC, fa.MFG_SITE) as region_name,
    
    -- Factory 層級
    fa.FACTORY as factory_code,
    fa.FACTORY_DESC as factory_name,
    
    -- Plant 層級
    mp.MFG_PLANT_CODE as plant_code,
    mp.MFG_PLANT_DESC as plant_name,
    
    -- Line 層級
    ld.LINE_NAME as line_code,
    ld.LINE_DESC as line_name

FROM bronze.common_mdm_line_desc_master ld
LEFT JOIN bronze.common_mdm_prod_area_master pa 
    ON ld.PROD_AREA_ID = pa.PROD_AREA_ID
LEFT JOIN bronze.common_mdm_factory_area_master fa 
    ON pa.FACTORY = fa.FACTORY
LEFT JOIN bronze.common_mdm_mfg_plant_master mp 
    ON fa.FACTORY = mp.FACTORY
LEFT JOIN bronze.common_mdm_mfg_site_master ms 
    ON fa.MFG_SITE = ms.MFG_SITE
```

---

## ✅ 驗證清單

- [x] Region 層級由 MDM_FACTORY_AREA_MASTER.MFG_SITE 提供
- [x] 所有 4 張核心 MDM 表已正確串接
- [x] 五階維度表已更新（silver.dim_mfg_five_level）
- [x] 資料品質達到 94.92% 有效率
- [x] 具體範例 V1-CNE-WJ2-PF-E5 已驗證

---

## 🚀 後續建議

### 立即可執行
1. ✅ 已完成：Silver 層五階維度表更新
2. 待執行：更新 Silver 層事實表的五階維度欄位
3. 待執行：更新 Gold 層指標計算邏輯

### 中期規劃
1. 驗證其他 Region-Factory-Plant-Line 組合
2. 建立 MDM 維度的資料品質監控
3. 整合業務邏輯與 MDM 維度的混合架構

### 長期規劃
1. 完全替換 Flowable 維度邏輯
2. 建立 MDM 維度的版本管理機制
3. 實施維度變更的影響評估流程

---

## 📝 相關文件

- `docs/mdm_table_requirements_summary.md` - MDM 表需求總結
- `docs/mdm_five_level_feasibility_analysis.md` - 可行性分析
- `sql/create_silver_dim_mfg_five_level.sql` - 實施 SQL
- `docs/metric_definitions.md` - 指標定義

---

**結論**: MDM 五階維度實施成功，Region 層級現已由 MDM_FACTORY_AREA_MASTER.MFG_SITE 提供，資料品質良好，可以進行後續的事實表和指標層更新。