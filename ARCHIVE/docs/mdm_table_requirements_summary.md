# MDM 表需求總結：五階維度 Region 由 MFG_SITE 提供

**分析日期：** 2026-01-21  
**目標五階結構：** V1 → Region(MFG_SITE) → Factory → Plant → Line  
**具體範例：** V1 → CNE(MFG_SITE) → WJ2(Factory) → NBU(Plant) → E5(Line)

---

## 📊 MDM 表使用需求

### 🟢 核心必需表（4張）

#### 1️⃣ **MDM_FACTORY_AREA_MASTER** ⭐ 核心表
- **用途**: 提供 Factory 和 Region(MFG_SITE) 關聯
- **必要性**: 🟢 **必需** - 核心串接表
- **關鍵欄位**: 
  - `FACTORY` (Factory 代碼)
  - `MFG_SITE` (Region 代碼 ← **直接作為五階 Region**)
  - `FACTORY_DESC` (Factory 描述)
- **串接角色**: Factory 層級主表，同時提供 Region 層級資訊

#### 2️⃣ **MDM_MFG_PLANT_MASTER**
- **用途**: 提供 Plant → Factory 關聯
- **必要性**: 🟢 **必需** - 核心串接表
- **關鍵欄位**:
  - `MFG_PLANT_CODE` (Plant 代碼)
  - `FACTORY` (Factory 代碼)
  - `MFG_PLANT_DESC` (Plant 描述)
- **串接角色**: Plant 層級主表，提供 Plant → Factory 關聯

#### 3️⃣ **MDM_PROD_AREA_MASTER**
- **用途**: 提供 ProdArea → Factory 關聯
- **必要性**: 🟢 **必需** - 核心串接表
- **關鍵欄位**:
  - `PROD_AREA_ID` (產區 ID)
  - `FACTORY` (Factory 代碼)
  - `PROD_AREA_CODE` (產區代碼)
- **串接角色**: 中間層，連接 Line 與 Factory

#### 4️⃣ **MDM_LINE_DESC_MASTER**
- **用途**: 提供 Line → ProdArea 關聯
- **必要性**: 🟢 **必需** - 核心串接表
- **關鍵欄位**:
  - `LINE_NAME` (產線名稱)
  - `PROD_AREA_ID` (產區 ID)
  - `LINE_DESC` (產線描述)
- **串接角色**: Line 層級主表，串接起點

### 🟡 可選增強表（1張）

#### 5️⃣ **MDM_MFG_SITE_MASTER** (可選)
- **用途**: 提供 Region(MFG_SITE) 的描述名稱
- **必要性**: 🟡 **可選** - 僅用於增強 Region 描述
- **關鍵欄位**:
  - `MFG_SITE` (Region 代碼)
  - `MFG_SITE_DESC` (Region 描述名稱)
- **串接角色**: 提供 Region 的友好名稱（可選）

### ❌ 不需要的表（1張）

#### 6️⃣ **MDM_BU_ORG_TYPE_MASTER**
- **用途**: BU 組織資訊
- **必要性**: ❌ **不需要** - 與五階維度無關
- **說明**: 此表提供 BU 組織架構資訊，與製造五階維度無直接關聯

---

## 🔗 串接路徑設計

### 完整串接邏輯
```
LINE_NAME → PROD_AREA_ID → FACTORY → MFG_SITE
    ↓           ↓           ↓         ↓
  Line      ProdArea     Factory    Region
```

### 五階維度對應
```
V1 (業務邏輯) → Region(MFG_SITE) → Factory → Plant → Line
                    ↓                ↓        ↓       ↓
                   CNE              WJ2      NBU     E5
```

### SQL 串接範例
```sql
SELECT 
    -- V1 層級 (業務邏輯)
    'V1' as vx_code,
    'V1' as vx_name,
    
    -- Region 層級 (直接由 MFG_SITE 提供)
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

## 📋 實施總結

### ✅ 核心需求
- **必需表數量**: 4 張核心表
- **可選表數量**: 1 張增強表（用於提供 Region 描述名稱）
- **總計使用**: 5 張表（已同步的 6 張中使用 5 張）

### 🎯 關鍵優勢
1. **結構簡潔**: 僅需 4 張核心表即可完成完整串接
2. **邏輯清晰**: 每張表職責明確，串接路徑直觀
3. **實證可行**: 基於 V1-CNE-WJ2-NBU-E5 實際驗證成功
4. **擴展性好**: 可輕鬆擴展到其他 Region-Factory-Plant-Line 組合
5. **Region 直接提供**: Region 層級直接由 MDM_FACTORY_AREA_MASTER.MFG_SITE 提供，無需額外轉換

### ⚠️ 注意事項
1. **Region 來源**: Region 層級直接由 MDM_FACTORY_AREA_MASTER 表的 MFG_SITE 欄位提供
2. **Vx 層級**: 仍需依賴業務邏輯（TaskDefinitionKey + MoNumber 規則）
3. **資料品質**: 需要監控 4 張核心表的資料完整性和一致性
4. **可選增強**: MDM_MFG_SITE_MASTER 可選，用於提供 Region 的友好名稱

### 🚀 建議行動
1. **立即可執行**: 基於 4 張核心表建立 Silver 層維度表
2. **優先驗證**: 擴展驗證其他 Region-Factory-Plant-Line 組合
3. **逐步完善**: 加入 MDM_MFG_SITE_MASTER 提供更友好的 Region 名稱

---

**結論**: 五階維度 Region 由 MDM_FACTORY_AREA_MASTER.MFG_SITE 直接提供的方案**技術可行性極高**，僅需 4 張核心 MDM 表即可完成完整的五階維度串接，建議立即開始實施。