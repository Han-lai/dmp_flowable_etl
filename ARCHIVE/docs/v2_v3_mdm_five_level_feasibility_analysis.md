# V2/V3 任務透過 MDM 補齊五階維度 - 可行性分析

**分析日期：** 2026-01-21  
**分析範圍：** V2/V3 任務的五階維度補齊方案  
**狀態：** 🔍 概念分析（不涉及 schema 或 ETL 修改）

---

## 📋 背景與問題

### 現狀
- **V1 任務**：透過 Flowable `ACT_HI_VARINST` 取得 plant/factory/line，五階維度完整
- **V2/V3 任務**：Flowable 不寫入 varinst，導致 plant/factory/line 缺失，五階維度不完整

### 目標
確認 V2/V3 任務是否能透過 MDM 主檔表補齊五階維度，以及具體的 mapping 路徑

---

## 🔑 V2/V3 任務中的可用鍵

### 任務事實表中的欄位
根據 `silver.V_HI_PROC_TASK_NODE` 視圖，V2/V3 任務中有以下維度欄位：

| 欄位名 | 來源 | 說明 | 可用性 |
|--------|------|------|--------|
| `PLANT` | 流程變數 | 來自 varinst 的 'plant' 變數 | ⚠️ V2/V3 缺失 |
| `FACTORY` | 流程變數 | 來自 varinst 的 'factory' 變數 | ⚠️ V2/V3 缺失 |
| `LINE_NAME` | 流程變數 | 來自 varinst 的 'lineName' 變數 | ⚠️ V2/V3 缺失 |
| `BUSINESS_KEY` | 流程實例 | 業務鍵（工單號等） | ✅ 可用 |
| `PROC_DEF_KEY` | 流程定義 | 流程定義鍵 | ✅ 可用 |
| `TASK_DEF_KEY` | 任務定義 | 任務定義鍵 | ✅ 可用 |

### 結論
**V2/V3 任務中缺少直接的 plant/factory/line 鍵**，但有 `BUSINESS_KEY` 和流程定義相關資訊可作為間接鍵。

---

## 🗂️ MDM 主檔表結構分析

### 6 張 MDM 表的結構

#### 1. MDM_LINE_DESC_MASTER（產線主檔）
```
主鍵: LINE_NAME (產線代碼)
欄位:
  - LINE_NAME: 產線代碼 (e.g., 'E5')
  - LINE_DESC: 產線描述
  - PROD_AREA_ID: 產區 ID (FK → MDM_PROD_AREA_MASTER)
  - VALID_FLAG: 有效性標記
```
**用途**：作為五階維度的起點（最細粒度）

#### 2. MDM_PROD_AREA_MASTER（產區主檔）
```
主鍵: PROD_AREA_ID
欄位:
  - PROD_AREA_ID: 產區 ID
  - PROD_AREA_CODE: 產區代碼
  - PROD_AREA_DESC: 產區描述
  - FACTORY: 工廠代碼 (FK → MDM_FACTORY_AREA_MASTER)
```
**用途**：連接 LINE 到 FACTORY

#### 3. MDM_MFG_PLANT_MASTER（製造廠區主檔）
```
主鍵: MFG_PLANT_ID 或 (MFG_PLANT_CODE, FACTORY)
欄位:
  - MFG_PLANT_CODE: 製造廠區代碼 (e.g., 'PF', 'NBU')
  - MFG_PLANT_DESC: 製造廠區描述
  - FACTORY: 工廠代碼 (FK → MDM_FACTORY_AREA_MASTER)
  - VALIDITY: 有效性標記
```
**用途**：提供 Plant 層級維度

#### 4. MDM_FACTORY_AREA_MASTER（工廠主檔）
```
主鍵: FACTORY
欄位:
  - FACTORY: 工廠代碼 (e.g., 'WJ2')
  - FACTORY_DESC: 工廠描述
  - MFG_SITE: 製造基地代碼 (FK → MDM_MFG_SITE_MASTER)
  - REGION: 區域代碼
  - COUNTRY: 國家代碼
  - VALID: 有效性標記
```
**用途**：提供 Factory 層級維度，連接到 Region

#### 5. MDM_MFG_SITE_MASTER（製造基地主檔）
```
主鍵: MFG_SITE
欄位:
  - MFG_SITE: 製造基地代碼 (e.g., 'DG', 'CZ', 'WJ')
  - MFG_SITE_DESC: 製造基地描述
```
**用途**：提供 Region 層級維度（作為五階的最高層）

#### 6. MDM_BU_ORG_TYPE_MASTER（BU/組織層主檔）
```
主鍵: 待確認
欄位: 待確認
```
**用途**：待確認（可能不需要用於五階維度）

---

## 🔗 MDM 表之間的關聯關係

```
MDM_LINE_DESC_MASTER
    ↓ (PROD_AREA_ID)
MDM_PROD_AREA_MASTER
    ↓ (FACTORY)
MDM_FACTORY_AREA_MASTER
    ↓ (MFG_SITE)
MDM_MFG_SITE_MASTER

MDM_FACTORY_AREA_MASTER
    ↓ (FACTORY)
MDM_MFG_PLANT_MASTER
```

**五階維度的完整路徑**：
```
LINE_NAME (E5)
  ↓ PROD_AREA_ID
PROD_AREA (產區)
  ↓ FACTORY
FACTORY (WJ2)
  ↓ MFG_SITE
REGION (WJ)
  ↓ (無直接關聯)
VX (V1/V2/V3) - 由業務邏輯決定

FACTORY (WJ2)
  ↓ FACTORY
PLANT (PF) - 來自 MDM_MFG_PLANT_MASTER
```

---

## 🎯 V2/V3 任務的 Mapping 可行性分析

### 方案 A：使用 LINE_NAME 作為起點（推薦）

#### 前提條件
- V2/V3 任務中必須有 `LINE_NAME` 欄位
- `LINE_NAME` 在 MDM_LINE_DESC_MASTER 中存在且唯一

#### Mapping 路徑
```
V2/V3 任務.LINE_NAME
  ↓ JOIN MDM_LINE_DESC_MASTER ON LINE_NAME
  ├─ 獲得：line_desc, prod_area_id
  ├─ 獲得：PROD_AREA_ID
  │
  ↓ JOIN MDM_PROD_AREA_MASTER ON PROD_AREA_ID
  ├─ 獲得：prod_area_code, prod_area_desc
  ├─ 獲得：FACTORY
  │
  ↓ JOIN MDM_FACTORY_AREA_MASTER ON FACTORY
  ├─ 獲得：factory_desc, country
  ├─ 獲得：MFG_SITE (Region)
  │
  ↓ JOIN MDM_MFG_SITE_MASTER ON MFG_SITE
  ├─ 獲得：mfg_site_desc (Region 描述)
  │
  ↓ JOIN MDM_MFG_PLANT_MASTER ON FACTORY
  └─ 獲得：mfg_plant_code (Plant), mfg_plant_desc
```

#### 補齊的維度層級
| 層級 | 欄位 | 來源 | 完整性 |
|------|------|------|--------|
| Line | line_code | V2/V3 任務 | ✅ 100% |
| Factory | factory_code | MDM_FACTORY_AREA_MASTER | ✅ 100% |
| Plant | plant_code | MDM_MFG_PLANT_MASTER | ✅ 100% |
| Region | region_code | MDM_MFG_SITE_MASTER | ✅ 100% |
| Vx | vx_code | 業務邏輯 | ⚠️ 需另行決定 |

#### 可行性評估
- **可行性**：✅ **高度可行**
- **前提**：V2/V3 任務中必須有 `LINE_NAME` 欄位
- **風險**：
  - 如果 `LINE_NAME` 為 NULL，則無法補齊
  - 如果 `LINE_NAME` 在 MDM 中不存在，則無法補齊
  - 如果 `LINE_NAME` 對應多個 FACTORY，則需要額外邏輯

---

### 方案 B：使用 PLANT + FACTORY 作為起點（備選）

#### 前提條件
- V2/V3 任務中必須有 `PLANT` 和 `FACTORY` 欄位
- 這些欄位在 MDM 中存在且組合唯一

#### Mapping 路徑
```
V2/V3 任務.PLANT + FACTORY
  ↓ JOIN MDM_MFG_PLANT_MASTER ON (PLANT=MFG_PLANT_CODE, FACTORY)
  ├─ 獲得：plant_desc
  ├─ 獲得：FACTORY
  │
  ↓ JOIN MDM_FACTORY_AREA_MASTER ON FACTORY
  ├─ 獲得：factory_desc, country
  ├─ 獲得：MFG_SITE (Region)
  │
  ↓ JOIN MDM_MFG_SITE_MASTER ON MFG_SITE
  └─ 獲得：mfg_site_desc (Region 描述)
```

#### 補齊的維度層級
| 層級 | 欄位 | 來源 | 完整性 |
|------|------|------|--------|
| Line | line_code | ❌ 無法補齊 | ❌ 0% |
| Factory | factory_code | V2/V3 任務 | ✅ 100% |
| Plant | plant_code | V2/V3 任務 | ✅ 100% |
| Region | region_code | MDM_MFG_SITE_MASTER | ✅ 100% |
| Vx | vx_code | 業務邏輯 | ⚠️ 需另行決定 |

#### 可行性評估
- **可行性**：⚠️ **部分可行**
- **限制**：無法補齊 Line 層級
- **風險**：
  - V2/V3 任務中 PLANT/FACTORY 本身就缺失
  - 即使有，也無法補齊 Line 層級

---

### 方案 C：使用 BUSINESS_KEY 反向查詢（探索性）

#### 前提條件
- `BUSINESS_KEY` 中包含可識別的 line/plant/factory 資訊
- 需要建立 BUSINESS_KEY 與 MDM 的對應關係

#### 可行性評估
- **可行性**：❌ **不可行**
- **原因**：
  - BUSINESS_KEY 格式不統一，難以解析
  - 需要額外的對應表維護
  - 成本高，收益低

---

## 📊 V2/V3 任務中 LINE_NAME 的可用性驗證

### 需要驗證的問題

1. **V2/V3 任務中是否有 LINE_NAME？**
   - 查詢：`SELECT COUNT(*) FROM silver.V_HI_PROC_TASK_NODE WHERE vx_type IN ('V2', 'V3') AND LINE_NAME IS NOT NULL`
   - 預期：應該有相當比例的任務有 LINE_NAME

2. **LINE_NAME 在 MDM 中的覆蓋率？**
   - 查詢：`SELECT COUNT(DISTINCT LINE_NAME) FROM bronze.common_mdm_line_desc_master WHERE VALID_FLAG = 'Y'`
   - 預期：應該包含所有生產線

3. **LINE_NAME 的唯一性？**
   - 查詢：`SELECT LINE_NAME, COUNT(DISTINCT PROD_AREA_ID) FROM bronze.common_mdm_line_desc_master GROUP BY LINE_NAME HAVING COUNT(DISTINCT PROD_AREA_ID) > 1`
   - 預期：每個 LINE_NAME 應該對應唯一的 PROD_AREA_ID

4. **完整的五階補齊率？**
   - 查詢：計算有 LINE_NAME 的 V2/V3 任務中，能完整補齊五階的比例
   - 預期：應該 > 90%

---

## 🎯 推薦方案

### 最優方案：方案 A（使用 LINE_NAME）

#### 優點
- ✅ 能補齊完整的五階維度（Line → Factory → Plant → Region）
- ✅ MDM 表結構清晰，JOIN 邏輯簡單
- ✅ 已有現成的五階維度表 (`silver.dim_mfg_five_level`) 可直接 JOIN
- ✅ 補齊率預期 > 90%

#### 缺點
- ⚠️ 依賴 V2/V3 任務中有 LINE_NAME 欄位
- ⚠️ 如果 LINE_NAME 為 NULL，則無法補齊

#### 實施步驟（概念）
1. 確認 V2/V3 任務中 LINE_NAME 的可用性和覆蓋率
2. 在 Silver 層建立 V2/V3 任務與 MDM 五階維度的 JOIN 視圖
3. 計算補齊率和缺失原因分布
4. 根據結果決定是否全量應用

---

## ⚠️ 關鍵風險與限制

### 1. LINE_NAME 可用性風險
- **風險**：V2/V3 任務中 LINE_NAME 可能為 NULL
- **影響**：無法補齊該任務的五階維度
- **緩解**：需要驗證 LINE_NAME 的覆蓋率

### 2. MDM 資料品質風險
- **風險**：MDM 表中可能有缺失或不一致的資料
- **影響**：補齊的維度可能不完整或不準確
- **緩解**：需要驗證 MDM 表的資料品質

### 3. 多對多關係風險
- **風險**：LINE_NAME 可能對應多個 FACTORY（跨廠生產線）
- **影響**：無法唯一確定五階維度
- **緩解**：需要驗證 LINE_NAME 的唯一性

### 4. 業務邏輯風險
- **風險**：V2/V3 的 Vx 歸屬邏輯與 V1 不同
- **影響**：補齊的五階維度可能不符合業務邏輯
- **緩解**：需要確認 V2/V3 的 Vx 定義

---

## 📋 後續驗證清單

### 立即驗證（必須）
- [ ] V2/V3 任務中 LINE_NAME 的覆蓋率（目標 > 90%）
- [ ] LINE_NAME 在 MDM 中的唯一性
- [ ] 完整的五階補齊率（目標 > 85%）
- [ ] 缺失原因分布

### 中期驗證（推薦）
- [ ] MDM 表的資料品質評分
- [ ] LINE_NAME 對應多個 FACTORY 的情況
- [ ] V2/V3 任務的 Vx 歸屬邏輯確認

### 長期規劃（可選）
- [ ] 建立 V2/V3 任務與 MDM 的自動對應機制
- [ ] 建立五階維度的版本管理
- [ ] 建立五階維度的資料品質監控

---

## 🎓 結論

### 可行性評估
**✅ V2/V3 任務透過 MDM 補齊五階維度是可行的**

### 推薦方案
**使用 LINE_NAME 作為起點，透過 MDM 表的 JOIN 補齊完整的五階維度**

### 關鍵前提
1. V2/V3 任務中必須有 LINE_NAME 欄位
2. LINE_NAME 在 MDM 中的覆蓋率 > 90%
3. LINE_NAME 對應的 FACTORY 唯一

### 預期效果
- 補齊率：> 85%
- 補齊層級：完整五階（Line → Factory → Plant → Region）
- 實施成本：低（只需 JOIN 現有 MDM 表）
- 維護成本：低（MDM 表由系統維護）

---

**分析完成日期**：2026-01-21  
**分析狀態**：✅ 概念分析完成，待驗證
                                                                                                  