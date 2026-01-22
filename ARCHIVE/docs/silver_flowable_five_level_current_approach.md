# Silver 層目前如何從 Flowable 取得五階資料

**分析日期：** 2026-01-21  
**分析範圍：** Silver 層的五階維度取得邏輯  
**狀態：** 📋 現狀分析

---

## 📋 概述

Silver 層目前透過以下方式從 Flowable 取得五階維度資料（plant/factory/line/region）：

### 資料流向
```
Bronze 層
  ├─ bronze.common_flowable_task_stats (FlowableTaskStats 表)
  │   ├─ Plant
  │   ├─ Factory
  │   └─ Line
  │
  ├─ bronze.bpm_act_hi_varinst (流程變數表)
  │   ├─ plant (變數名)
  │   ├─ factory (變數名)
  │   ├─ lineName (變數名)
  │   └─ region (變數名)
  │
  └─ bronze.bpm_act_hi_procinst (流程實例表)
      └─ BUSINESS_KEY_

        ↓

Silver 層
  ├─ silver.V_PROC_VARIABLES_PIVOTED (流程變數樞紐視圖)
  │   ├─ PLANT
  │   ├─ FACTORY
  │   ├─ LINE_NAME
  │   └─ REGION
  │
  ├─ silver.V_HI_PROC_TASK_NODE (任務節點視圖)
  │   ├─ PLANT (來自 V_PROC_VARIABLES_PIVOTED)
  │   ├─ FACTORY (來自 V_PROC_VARIABLES_PIVOTED)
  │   ├─ LINE_NAME (來自 V_PROC_VARIABLES_PIVOTED)
  │   └─ REGION (來自 V_PROC_VARIABLES_PIVOTED)
  │
  └─ silver.FACT_TASK_VX_ATTRIBUTION (任務事實表)
      ├─ plant (來自 FlowableTaskStats)
      ├─ factory (來自 FlowableTaskStats)
      ├─ line (來自 FlowableTaskStats)
      └─ region (推導或 fallback)
```

---

## 🔍 1. 詳細的五階資料取得邏輯

### 1.1 流程變數樞紐視圖：V_PROC_VARIABLES_PIVOTED

**位置**：`sql/05_create_silver_views.sql`

**功能**：將 `bronze.bpm_act_hi_varinst` 的行轉列，提取流程層級的五階變數

**SQL 邏輯**：
```sql
CREATE VIEW silver.V_PROC_VARIABLES_PIVOTED AS
SELECT
    PROC_INST_ID_ AS PROC_INST_ID,
    anyIf(TEXT_, NAME_ = 'plant') AS PLANT,
    anyIf(TEXT_, NAME_ = 'factory') AS FACTORY,
    anyIf(TEXT_, NAME_ = 'region') AS REGION,
    anyIf(TEXT_, NAME_ = 'lineName') AS LINE_NAME,
    -- ... 其他變數
FROM bronze.bpm_act_hi_varinst
WHERE NAME_ IN ('plant', 'factory', 'region', 'lineName', ...)
  AND PROC_INST_ID_ IS NOT NULL
  AND TASK_ID_ IS NULL  -- 只取流程層級變數，不取任務層級
GROUP BY PROC_INST_ID_
```

**關鍵特性**：
- ✅ 使用 `anyIf()` 函數進行行轉列
- ✅ 只取 `TASK_ID_ IS NULL` 的記錄（流程層級變數）
- ✅ 提取的變數名：`plant`, `factory`, `region`, `lineName`
- ⚠️ **限制**：只有 V1 流程會寫入 varinst，V2/V3 流程不寫入

**資料覆蓋率**：
- V1 流程：✅ 100%（都有 varinst 變數）
- V2/V3 流程：❌ 0%（不寫入 varinst）

---

### 1.2 任務節點視圖：V_HI_PROC_TASK_NODE

**位置**：`sql/05_create_silver_views.sql`

**功能**：將任務與流程變數進行 JOIN，為每個任務補齊五階維度

**SQL 邏輯**：
```sql
CREATE VIEW silver.V_HI_PROC_TASK_NODE AS
SELECT
    t.ID_ AS TASK_ID,
    t.PROC_INST_ID_ AS PROC_INST_ID,
    -- ... 其他任務欄位
    
    -- 流程層變數（來自 V_PROC_VARIABLES_PIVOTED）
    v.PLANT,
    v.FACTORY,
    v.REGION,
    v.LINE_NAME,
    -- ... 其他變數

FROM bronze.bpm_act_hi_taskinst AS t
LEFT JOIN bronze.bpm_act_hi_procinst AS p ON t.PROC_INST_ID_ = p.PROC_INST_ID_
LEFT JOIN silver.V_PROC_VARIABLES_PIVOTED AS v ON t.PROC_INST_ID_ = v.PROC_INST_ID
-- ... 其他 JOIN
```

**關鍵特性**：
- ✅ 透過 `PROC_INST_ID_` 進行 LEFT JOIN
- ✅ 將流程層變數附加到每個任務
- ⚠️ **限制**：V2/V3 任務的 PLANT/FACTORY/LINE_NAME 為 NULL（因為 varinst 中沒有）

**資料覆蓋率**：
- V1 任務：✅ 100%（都有 varinst 變數）
- V2/V3 任務：❌ 0%（varinst 中沒有變數）

---

### 1.3 任務事實表：FACT_TASK_VX_ATTRIBUTION

**位置**：`scripts/transform_silver_generic_metrics.py`

**功能**：將 Bronze 層資料轉換為 Silver 層事實表，包含五階維度

**SQL 邏輯**：
```sql
INSERT INTO silver.FACT_TASK_VX_ATTRIBUTION
WITH 
-- 從 varinst 轉置取得 moNumber 和維度資訊
varinst_pivoted AS (
    SELECT 
        PROC_INST_ID_,
        MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber,
        MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS varinst_plant,
        MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS varinst_factory,
        MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS varinst_lineName
    FROM bronze.bpm_act_hi_varinst
    WHERE NAME_ IN ('moNumber', 'plant', 'factory', 'lineName')
    GROUP BY PROC_INST_ID_
)
SELECT
    -- 主鍵
    t.TaskId AS task_id,
    
    -- 時間維度
    COALESCE(t.TaskCreateDate, toDate('1970-01-01')) AS task_create_date,
    
    -- 五階維度：優先使用 MDM，Flowable 作為 fallback
    COALESCE(dim.region_code, ...) AS region_code,
    COALESCE(dim.plant_code, COALESCE(v.varinst_plant, t.Plant)) AS plant_code,
    COALESCE(dim.factory_code, COALESCE(v.varinst_factory, t.Factory)) AS factory_code,
    COALESCE(dim.line_name, COALESCE(v.varinst_lineName, t.Line)) AS line_code,
    
    -- 維度資料來源標記
    CASE 
        WHEN dim.line_name IS NOT NULL THEN 'MDM_COMPLETE'
        WHEN COALESCE(v.varinst_lineName, t.Line) IS NOT NULL THEN 'MDM_NO_MATCH_USE_FLOWABLE_FALLBACK'
        ELSE 'MDM_AND_FLOWABLE_BOTH_MISSING'
    END AS dimension_source,
    
    -- 維度（ORDER BY 用）
    t.Plant AS plant,
    t.Factory AS factory,
    t.Line AS line,
    
    -- ... 其他欄位

FROM bronze.common_flowable_task_stats t
LEFT JOIN bronze.bpm_act_hi_procinst p ON t.ProcessInstanceId = p.PROC_INST_ID_
LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
LEFT JOIN silver.dim_mfg_five_level dim ON COALESCE(v.varinst_lineName, t.Line) = dim.line_name
WHERE t.TaskId IS NOT NULL AND t.TaskId != ''
```

**關鍵特性**：
- ✅ 優先使用 MDM 維度表（`silver.dim_mfg_five_level`）
- ✅ 如果 MDM 無法補齊，使用 Flowable 的 varinst 變數
- ✅ 如果 varinst 也沒有，使用 FlowableTaskStats 表中的欄位
- ✅ 記錄資料來源（MDM_COMPLETE / MDM_NO_MATCH_USE_FLOWABLE_FALLBACK / MDM_AND_FLOWABLE_BOTH_MISSING）

**優先順序**：
```
1. MDM 維度表 (silver.dim_mfg_five_level)
   ↓ (如果 MDM 無法補齊)
2. Flowable varinst 變數 (v.varinst_plant, v.varinst_factory, v.varinst_lineName)
   ↓ (如果 varinst 也沒有)
3. FlowableTaskStats 表欄位 (t.Plant, t.Factory, t.Line)
```

---

## 📊 2. 五階資料的來源分析

### 2.1 Plant 欄位的來源

| 來源 | 優先級 | 適用對象 | 覆蓋率 |
|------|--------|----------|--------|
| MDM_MFG_PLANT_MASTER | 1️⃣ 優先 | 所有任務 | 取決於 line_name 在 MDM 中的覆蓋率 |
| varinst.plant | 2️⃣ 次優 | V1 任務 | ✅ 100% (V1 都有 varinst) |
| FlowableTaskStats.Plant | 3️⃣ 備用 | 所有任務 | ⚠️ 可能為 NULL 或不完整 |

### 2.2 Factory 欄位的來源

| 來源 | 優先級 | 適用對象 | 覆蓋率 |
|------|--------|----------|--------|
| MDM_FACTORY_AREA_MASTER | 1️⃣ 優先 | 所有任務 | 取決於 line_name 在 MDM 中的覆蓋率 |
| varinst.factory | 2️⃣ 次優 | V1 任務 | ✅ 100% (V1 都有 varinst) |
| FlowableTaskStats.Factory | 3️⃣ 備用 | 所有任務 | ⚠️ 可能為 NULL 或不完整 |

### 2.3 Line 欄位的來源

| 來源 | 優先級 | 適用對象 | 覆蓋率 |
|------|--------|----------|--------|
| MDM_LINE_DESC_MASTER | 1️⃣ 優先 | 所有任務 | 取決於 line_name 在 MDM 中的覆蓋率 |
| varinst.lineName | 2️⃣ 次優 | V1 任務 | ✅ 100% (V1 都有 varinst) |
| FlowableTaskStats.Line | 3️⃣ 備用 | 所有任務 | ⚠️ 可能為 NULL 或不完整 |

### 2.4 Region 欄位的來源

| 來源 | 優先級 | 適用對象 | 覆蓋率 |
|------|--------|----------|--------|
| MDM_MFG_SITE_MASTER | 1️⃣ 優先 | 所有任務 | 取決於 line_name 在 MDM 中的覆蓋率 |
| varinst.region | 2️⃣ 次優 | V1 任務 | ⚠️ 可能為 NULL（不是所有 V1 都有） |
| 推導邏輯 | 3️⃣ 備用 | 所有任務 | ⚠️ 基於 plant 代碼的簡單對應 |

---

## 🎯 3. V1 vs V2/V3 的五階資料可用性

### 3.1 V1 任務的五階資料取得

```
V1 任務
  ↓
Flowable 寫入 ACT_HI_VARINST
  ├─ plant = 'PF'
  ├─ factory = 'WJ2'
  ├─ lineName = 'E5'
  └─ region = 'WJ'
  ↓
Silver 層 V_PROC_VARIABLES_PIVOTED
  ├─ PLANT = 'PF'
  ├─ FACTORY = 'WJ2'
  ├─ LINE_NAME = 'E5'
  └─ REGION = 'WJ'
  ↓
Silver 層 FACT_TASK_VX_ATTRIBUTION
  ├─ plant = 'PF' ✅
  ├─ factory = 'WJ2' ✅
  ├─ line = 'E5' ✅
  └─ region = 'WJ' ✅
```

**覆蓋率**：✅ 100%（所有 V1 任務都有完整五階）

---

### 3.2 V2/V3 任務的五階資料取得

```
V2/V3 任務
  ↓
Flowable 不寫入 ACT_HI_VARINST
  ├─ plant = NULL
  ├─ factory = NULL
  ├─ lineName = NULL
  └─ region = NULL
  ↓
Silver 層 V_PROC_VARIABLES_PIVOTED
  ├─ PLANT = NULL ❌
  ├─ FACTORY = NULL ❌
  ├─ LINE_NAME = NULL ❌
  └─ REGION = NULL ❌
  ↓
Silver 層 FACT_TASK_VX_ATTRIBUTION
  ├─ plant = NULL ❌ (無法從 varinst 取得)
  ├─ factory = NULL ❌ (無法從 varinst 取得)
  ├─ line = NULL ❌ (無法從 varinst 取得)
  └─ region = NULL ❌ (無法從 varinst 取得)
```

**覆蓋率**：❌ 0%（所有 V2/V3 任務都缺少五階）

---

## ⚠️ 4. 當前方案的限制

### 4.1 V1 任務的限制

| 限制 | 說明 | 影響 |
|------|------|------|
| varinst 可能為 NULL | 某些 V1 流程可能沒有寫入 varinst | 五階缺失 |
| varinst 資料不完整 | 某些變數可能沒有寫入 | 五階部分缺失 |
| varinst 資料不準確 | 變數值可能與實際不符 | 五階維度不準確 |

### 4.2 V2/V3 任務的限制

| 限制 | 說明 | 影響 |
|------|------|------|
| **Flowable 不寫入 varinst** | V2/V3 流程完全不寫入 varinst | ❌ 無法透過 varinst 取得五階 |
| FlowableTaskStats 可能為 NULL | Plant/Factory/Line 欄位可能為 NULL | ❌ 無法透過 FlowableTaskStats 取得五階 |
| 無法從 MDM 推導 | 沒有 line_name 作為 join key | ❌ 無法透過 MDM 補齊五階 |

---

## 🔗 5. 當前方案與 MDM 的整合

### 5.1 MDM 維度表的使用

**表名**：`silver.dim_mfg_five_level`

**建立方式**：基於 MDM 主檔表的 JOIN 邏輯

**使用方式**：
```sql
LEFT JOIN silver.dim_mfg_five_level dim 
    ON COALESCE(v.varinst_lineName, t.Line) = dim.line_name
```

**補齊邏輯**：
```
IF line_name 在 MDM 中存在
  THEN 使用 MDM 維度（plant/factory/region）
  ELSE 使用 Flowable 的 varinst 或 FlowableTaskStats
```

### 5.2 MDM 補齊的效果

根據 `docs/l5_metrics_validation_wj2_nbu_e5.md`：

| 指標 | 數值 |
|------|------|
| 總任務數 | 1,300,963 |
| 五階完整任務 | 1,115,818 |
| 完整率 | 85.77% |

**結論**：MDM 補齊已經提升了五階維度的完整率到 85.77%

---

## 📋 6. 總結：Silver 層目前的五階資料取得方式

### 6.1 資料流向

```
Bronze 層
  ├─ FlowableTaskStats (Plant/Factory/Line)
  ├─ ACT_HI_VARINST (plant/factory/lineName/region 變數)
  └─ ACT_HI_PROCINST (BUSINESS_KEY_)
    ↓
Silver 層視圖
  ├─ V_PROC_VARIABLES_PIVOTED (varinst 行轉列)
  └─ V_HI_PROC_TASK_NODE (任務 + 流程變數 JOIN)
    ↓
Silver 層事實表
  └─ FACT_TASK_VX_ATTRIBUTION
      ├─ 優先使用 MDM 維度表
      ├─ 次優使用 varinst 變數（V1 only）
      └─ 備用使用 FlowableTaskStats 欄位
```

### 6.2 V1 vs V2/V3 的覆蓋率

| 流程類型 | varinst 覆蓋 | MDM 補齊後 | 說明 |
|---------|-------------|-----------|------|
| **V1** | ✅ 100% | ✅ 100% | 完整五階 |
| **V2/V3** | ❌ 0% | ⚠️ 部分 | 需要透過 MDM 補齊 |

### 6.3 當前的五階補齊優先順序

```
1️⃣ MDM 維度表 (silver.dim_mfg_five_level)
   - 基於 line_name 的 JOIN
   - 補齊率：85.77%

2️⃣ Flowable varinst 變數
   - 僅適用於 V1 任務
   - 覆蓋率：100% (V1 only)

3️⃣ FlowableTaskStats 欄位
   - 備用方案
   - 覆蓋率：不確定（可能為 NULL）
```

---

## 🎯 關鍵發現

### ✅ 已實施的方案
1. MDM 維度表已建立並整合到 Silver 層
2. 五階補齊優先順序已定義（MDM > varinst > FlowableTaskStats）
3. 資料來源已標記（MDM_COMPLETE / MDM_NO_MATCH_USE_FLOWABLE_FALLBACK / MDM_AND_FLOWABLE_BOTH_MISSING）

### ⚠️ 當前的限制
1. V2/V3 任務無法透過 varinst 取得五階（Flowable 不寫入）
2. V2/V3 任務的五階補齊完全依賴 MDM 和 FlowableTaskStats
3. 如果 line_name 為 NULL，則無法透過 MDM 補齊

### ❓ 待確認的問題
1. V2/V3 任務中 line_name 的覆蓋率是多少？
2. FlowableTaskStats 中 Plant/Factory/Line 的覆蓋率是多少？
3. 是否有其他方式可以為 V2/V3 任務補齊五階？

---

**分析完成日期**：2026-01-21  
**分析狀態**：✅ 現狀分析完成
