# MSSQL 五階資料與 Vx 邏輯來源分析

**分析日期：** 2026-01-21  
**分析範圍：** MSSQL 中可取得五階資料的表，以及 Vx 邏輯出現的表  
**前提條件：** 不使用 ACT_HI_VARINST 表  
**狀態：** 📋 現狀分析

---

## 📋 概述

本分析基於 `docs/metric_definitions.md` 的定義，確認 MSSQL 中哪些表可以直接取得五階資料（Plant/Factory/Line/Region），以及 Vx 邏輯出現在哪些表中。

---

## 🔍 1. 五階資料來源分析

### 1.1 五階維度定義

根據 `metric_definitions.md`：

```
製造五階定義：Region → Vx → Plant → Factory → Line
```

**Flowable 本身提供的欄位**：
- ✅ Plant
- ✅ Factory / Production Area
- ✅ Line

**Flowable 不提供的欄位**：
- ❌ Region（必須從 MDM 補齊）
- ❌ Vx（由業務邏輯決定）

---

### 1.2 MSSQL 中可取得五階資料的表

#### 表 1：APP_SRV_BPM.dbo.ACT_HI_TASKINST（任務實例表）

**表說明**：Flowable 任務歷史表，記錄所有任務的執行歷史

**可取得的五階欄位**：
- ❌ Plant：不直接存在
- ❌ Factory：不直接存在
- ❌ Line：不直接存在
- ❌ Region：不存在

**相關欄位**：
- `TASK_DEF_KEY_`：任務定義鍵（用於 Vx 判斷）
- `PROC_INST_ID_`：流程實例 ID（用於 JOIN 其他表）
- `START_TIME_`：任務開始時間
- `CLAIM_TIME_`：任務認領時間
- `END_TIME_`：任務結束時間
- `ASSIGNEE_`：任務指派人

**結論**：❌ 不能直接取得五階資料，但可透過 PROC_INST_ID_ JOIN 其他表

---

#### 表 2：APP_SRV_BPM.dbo.ACT_HI_PROCINST（流程實例表）

**表說明**：Flowable 流程實例歷史表，記錄所有流程的執行歷史

**可取得的五階欄位**：
- ❌ Plant：不直接存在
- ❌ Factory：不直接存在
- ❌ Line：不直接存在
- ❌ Region：不存在

**相關欄位**：
- `PROC_INST_ID_`：流程實例 ID
- `BUSINESS_KEY_`：業務鍵（用於 NPE 判斷）
- `NAME_`：流程名稱（可能包含工單編號等資訊）
- `START_TIME_`：流程開始時間
- `END_TIME_`：流程結束時間

**結論**：❌ 不能直接取得五階資料

---

#### 表 3：APP_SRV_BPM.dbo.ACT_HI_VARINST（流程變數表）

**表說明**：Flowable 流程變數歷史表，記錄所有流程變數（EAV 結構）

**可取得的五階欄位**（需轉置）：
- ✅ Plant：`TEXT_` WHERE `NAME_ = 'plant'`
- ✅ Factory：`TEXT_` WHERE `NAME_ = 'factory'`
- ✅ Line：`TEXT_` WHERE `NAME_ = 'lineName'`
- ⚠️ Region：`TEXT_` WHERE `NAME_ = 'region'`（可能為 NULL）

**相關欄位**：
- `PROC_INST_ID_`：流程實例 ID
- `TASK_ID_`：任務 ID（NULL 表示流程層級變數）
- `NAME_`：變數名稱
- `TEXT_`：變數值

**轉置後的變數名稱**：
- `plant`：製造廠區代碼
- `factory`：工廠代碼
- `lineName`：產線代碼
- `region`：區域代碼
- `moNumber`：工單編號（用於 Vx 判斷）

**限制**：
- ⚠️ **只有 V1 流程才會寫入 varinst**
- ❌ V2/V3 流程不寫入 varinst

**結論**：✅ 能取得五階資料，但**僅限 V1 流程**

---

#### 表 4：APP_SRV_COMMON.dbo.FlowableTaskStats（任務統計表）

**表說明**：DMP 系統中的任務統計表，可能是從 Flowable 同步或計算得出

**可取得的五階欄位**：
- ✅ Plant：`Plant` 欄位
- ✅ Factory：`Factory` 欄位
- ✅ Line：`Line` 欄位
- ❌ Region：不存在

**相關欄位**：
- `Plant`：製造廠區代碼
- `Factory`：工廠代碼
- `Line`：產線代碼
- `MoNumber`：工單編號（用於 Vx 判斷）
- `TaskDefinitionKey`：任務定義鍵（用於 Vx 判斷）
- `TaskStatus`：任務狀態
- `TaskCreateTime`：任務建立時間

**覆蓋率**：
- ⚠️ 可能為 NULL（不是所有任務都有這些欄位）
- ⚠️ 資料可能不完整或不準確

**結論**：⚠️ 能取得五階資料，但**可能不完整或不準確**

---

### 1.3 五階資料來源優先順序（不使用 ACT_HI_VARINST）

```
1️⃣ MDM 主檔表（需要 line_name 作為 join key）
   ├─ MDM_LINE_DESC_MASTER
   ├─ MDM_PROD_AREA_MASTER
   ├─ MDM_MFG_PLANT_MASTER
   ├─ MDM_FACTORY_AREA_MASTER
   └─ MDM_MFG_SITE_MASTER
   
2️⃣ FlowableTaskStats 表
   ├─ Plant
   ├─ Factory
   └─ Line
   
3️⃣ 其他表（不推薦）
   └─ ACT_HI_PROCINST（只有 BUSINESS_KEY_，無直接五階資訊）
```

---

## 🎯 2. Vx 邏輯來源分析

### 2.1 Vx 邏輯的定義

根據 `metric_definitions.md` 的修正邏輯（2026-01-21）：

```sql
CASE 
    WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
    WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
    -- 特定 315% 工單號歸類為 V1
    WHEN moNumber IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
    WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
    -- 其他工單號規則
    WHEN moNumber LIKE '196%' OR moNumber LIKE '199%' OR moNumber LIKE '200%'
         OR moNumber LIKE '210%' OR moNumber LIKE '212%' OR moNumber LIKE '213%'
    THEN 'V1'
    ELSE COALESCE(substring(TaskDefinitionKey, 1, 2), 'Unknown')
END
```

### 2.2 Vx 邏輯出現的表

#### 表 1：APP_SRV_BPM.dbo.ACT_HI_TASKINST

**Vx 相關欄位**：
- ✅ `TASK_DEF_KEY_`：任務定義鍵（用於判斷 V1/V2/V3 前綴）

**Vx 判斷邏輯**：
```sql
CASE 
    WHEN TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
    WHEN TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
    WHEN TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
    ELSE COALESCE(substring(TASK_DEF_KEY_, 1, 2), 'Unknown')
END
```

**覆蓋率**：✅ 100%（所有任務都有 TASK_DEF_KEY_）

**結論**：✅ 能取得基本的 Vx 邏輯（基於 TaskDefinitionKey 前綴）

---

#### 表 2：APP_SRV_BPM.dbo.ACT_HI_VARINST

**Vx 相關欄位**：
- ✅ `TEXT_` WHERE `NAME_ = 'moNumber'`：工單編號（用於特殊規則判斷）

**Vx 判斷邏輯**：
```sql
-- 特定 315% 工單號歸類為 V1
CASE 
    WHEN moNumber IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
    WHEN moNumber LIKE '196%' OR moNumber LIKE '199%' OR moNumber LIKE '200%'
         OR moNumber LIKE '210%' OR moNumber LIKE '212%' OR moNumber LIKE '213%'
    THEN 'V1'
    ELSE NULL
END
```

**限制**：
- ⚠️ **只有 V1 流程才會寫入 varinst**
- ❌ V2/V3 流程無法透過此表取得 moNumber

**結論**：⚠️ 能取得特殊規則的 Vx 邏輯，但**僅限 V1 流程**

---

#### 表 3：APP_SRV_COMMON.dbo.FlowableTaskStats

**Vx 相關欄位**：
- ✅ `TaskDefinitionKey`：任務定義鍵
- ✅ `MoNumber`：工單編號

**Vx 判斷邏輯**：
```sql
CASE 
    WHEN TaskDefinitionKey LIKE 'V1%' THEN 'V1'
    WHEN TaskDefinitionKey LIKE 'V2%' THEN 'V2'
    WHEN MoNumber IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
    WHEN TaskDefinitionKey LIKE 'V3%' THEN 'V3'
    WHEN MoNumber LIKE '196%' OR MoNumber LIKE '199%' OR MoNumber LIKE '200%'
         OR MoNumber LIKE '210%' OR MoNumber LIKE '212%' OR MoNumber LIKE '213%'
    THEN 'V1'
    ELSE COALESCE(substring(TaskDefinitionKey, 1, 2), 'Unknown')
END
```

**覆蓋率**：
- ✅ TaskDefinitionKey：100%
- ⚠️ MoNumber：可能為 NULL

**結論**：✅ 能取得完整的 Vx 邏輯（包括特殊規則）

---

#### 表 4：APP_SRV_BPM.dbo.ACT_HI_PROCINST

**Vx 相關欄位**：
- ⚠️ `BUSINESS_KEY_`：業務鍵（用於 NPE 判斷，不直接用於 Vx 判斷）
- ❌ 無直接的 Vx 判斷欄位

**結論**：❌ 不能直接取得 Vx 邏輯

---

### 2.3 Vx 邏輯的完整來源

| Vx 判斷條件 | 來源表 | 欄位 | 覆蓋率 |
|-----------|--------|------|--------|
| **TaskDefinitionKey 前綴** | ACT_HI_TASKINST | TASK_DEF_KEY_ | ✅ 100% |
| **TaskDefinitionKey 前綴** | FlowableTaskStats | TaskDefinitionKey | ✅ 100% |
| **特定 315% 工單號** | ACT_HI_VARINST | moNumber | ⚠️ V1 only |
| **特定 315% 工單號** | FlowableTaskStats | MoNumber | ⚠️ 可能 NULL |
| **其他工單號規則** | ACT_HI_VARINST | moNumber | ⚠️ V1 only |
| **其他工單號規則** | FlowableTaskStats | MoNumber | ⚠️ 可能 NULL |

---

## 📊 3. 不使用 ACT_HI_VARINST 的影響分析

### 3.1 失去的功能

如果不使用 ACT_HI_VARINST，會失去以下功能：

| 功能 | 影響 | 替代方案 |
|------|------|---------|
| **V1 流程的五階資料** | ❌ 無法取得 plant/factory/line | 使用 FlowableTaskStats 或 MDM |
| **特定工單號的 Vx 判斷** | ⚠️ 依賴 FlowableTaskStats.MoNumber | 使用 FlowableTaskStats |
| **Region 資訊** | ❌ 無法取得 | 使用 MDM 補齊 |

### 3.2 可用的替代方案

#### 方案 A：使用 FlowableTaskStats 表

**優點**：
- ✅ 包含 Plant/Factory/Line 欄位
- ✅ 包含 MoNumber 欄位（用於 Vx 判斷）
- ✅ 包含 TaskDefinitionKey 欄位

**缺點**：
- ⚠️ Plant/Factory/Line 可能為 NULL
- ⚠️ MoNumber 可能為 NULL
- ⚠️ 資料可能不完整或不準確

**適用場景**：
- V2/V3 流程（因為 varinst 中沒有資料）
- 需要快速取得五階資料的場景

---

#### 方案 B：使用 MDM 主檔表

**優點**：
- ✅ 資料完整且準確
- ✅ 包含 Region 資訊
- ✅ 適用於所有流程類型

**缺點**：
- ⚠️ 需要 line_name 作為 join key
- ⚠️ 如果 line_name 為 NULL，則無法補齊

**適用場景**：
- 需要準確的五階資料
- 需要 Region 資訊
- 可以接受部分資料無法補齊的情況

---

#### 方案 C：混合方案（推薦）

**邏輯**：
```
1️⃣ 優先使用 MDM 主檔表（基於 line_name）
2️⃣ 如果 MDM 無法補齊，使用 FlowableTaskStats
3️⃣ 如果都無法補齊，標記為缺失
```

**優點**：
- ✅ 最大化資料覆蓋率
- ✅ 優先使用準確的 MDM 資料
- ✅ 適用於所有流程類型

**缺點**：
- ⚠️ 邏輯複雜
- ⚠️ 需要多表 JOIN

---

## 🔗 4. 不使用 ACT_HI_VARINST 的 SQL 範例

### 4.1 取得五階資料（不使用 varinst）

```sql
-- 方案：使用 FlowableTaskStats + MDM
SELECT 
    t.TaskId,
    t.TaskDefinitionKey,
    t.TaskStatus,
    
    -- 五階維度：優先使用 MDM，FlowableTaskStats 作為 fallback
    COALESCE(dim.region_code, 'UNKNOWN') AS region_code,
    COALESCE(dim.plant_code, t.Plant) AS plant_code,
    COALESCE(dim.factory_code, t.Factory) AS factory_code,
    COALESCE(dim.line_code, t.Line) AS line_code,
    
    -- 資料來源標記
    CASE 
        WHEN dim.line_code IS NOT NULL THEN 'MDM_COMPLETE'
        WHEN t.Line IS NOT NULL THEN 'FLOWABLE_FALLBACK'
        ELSE 'MISSING'
    END AS dimension_source

FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
LEFT JOIN MDM_DIM_FIVE_LEVEL dim 
    ON t.Line = dim.line_code
WHERE t.TaskId IS NOT NULL
```

### 4.2 取得 Vx 邏輯（不使用 varinst）

```sql
-- 方案：使用 FlowableTaskStats 中的 TaskDefinitionKey 和 MoNumber
SELECT 
    t.TaskId,
    t.TaskDefinitionKey,
    t.MoNumber,
    
    -- Vx 邏輯
    CASE 
        WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1'
        WHEN t.TaskDefinitionKey LIKE 'V2%' THEN 'V2'
        WHEN t.MoNumber IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
        WHEN t.TaskDefinitionKey LIKE 'V3%' THEN 'V3'
        WHEN t.MoNumber LIKE '196%' OR t.MoNumber LIKE '199%' OR t.MoNumber LIKE '200%'
             OR t.MoNumber LIKE '210%' OR t.MoNumber LIKE '212%' OR t.MoNumber LIKE '213%'
        THEN 'V1'
        ELSE COALESCE(SUBSTRING(t.TaskDefinitionKey, 1, 2), 'Unknown')
    END AS vx_type

FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
WHERE t.TaskId IS NOT NULL
```

### 4.3 完整的五階 + Vx 查詢（不使用 varinst）

```sql
-- 完整查詢：五階 + Vx + 任務狀態
SELECT 
    t.TaskId,
    t.TaskCreateDate,
    t.TaskStatus,
    
    -- Vx 邏輯
    CASE 
        WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1'
        WHEN t.TaskDefinitionKey LIKE 'V2%' THEN 'V2'
        WHEN t.MoNumber IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
        WHEN t.TaskDefinitionKey LIKE 'V3%' THEN 'V3'
        WHEN t.MoNumber LIKE '196%' OR t.MoNumber LIKE '199%' OR t.MoNumber LIKE '200%'
             OR t.MoNumber LIKE '210%' OR t.MoNumber LIKE '212%' OR t.MoNumber LIKE '213%'
        THEN 'V1'
        ELSE COALESCE(SUBSTRING(t.TaskDefinitionKey, 1, 2), 'Unknown')
    END AS vx_type,
    
    -- 五階維度
    COALESCE(dim.region_code, 'UNKNOWN') AS region_code,
    COALESCE(dim.plant_code, t.Plant) AS plant_code,
    COALESCE(dim.factory_code, t.Factory) AS factory_code,
    COALESCE(dim.line_code, t.Line) AS line_code,
    
    -- 資料來源
    CASE 
        WHEN dim.line_code IS NOT NULL THEN 'MDM_COMPLETE'
        WHEN t.Line IS NOT NULL THEN 'FLOWABLE_FALLBACK'
        ELSE 'MISSING'
    END AS dimension_source

FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
LEFT JOIN MDM_DIM_FIVE_LEVEL dim 
    ON t.Line = dim.line_code
WHERE t.TaskId IS NOT NULL
  AND t.TaskCreateDate >= '2025-12-28'
ORDER BY t.TaskCreateDate DESC, t.TaskId
```

---

## 📋 5. 總結

### 5.1 MSSQL 中可取得五階資料的表

| 表名 | Plant | Factory | Line | Region | 覆蓋率 | 說明 |
|------|--------|---------|------|--------|--------|------|
| **ACT_HI_VARINST** | ✅ | ✅ | ✅ | ⚠️ | ⚠️ V1 only | 需轉置，僅 V1 流程 |
| **FlowableTaskStats** | ✅ | ✅ | ✅ | ❌ | ⚠️ 可能 NULL | 直接欄位，可能不完整 |
| **MDM 主檔表** | ✅ | ✅ | ✅ | ✅ | ✅ 85%+ | 需 line_name join key |
| **ACT_HI_TASKINST** | ❌ | ❌ | ❌ | ❌ | ❌ | 無直接五階欄位 |
| **ACT_HI_PROCINST** | ❌ | ❌ | ❌ | ❌ | ❌ | 無直接五階欄位 |

### 5.2 Vx 邏輯出現的表

| 表名 | TaskDefinitionKey | MoNumber | 覆蓋率 | 說明 |
|------|-------------------|----------|--------|------|
| **ACT_HI_TASKINST** | ✅ | ❌ | ✅ 100% | 基本 Vx 邏輯 |
| **FlowableTaskStats** | ✅ | ✅ | ✅ 100% | 完整 Vx 邏輯 |
| **ACT_HI_VARINST** | ❌ | ✅ | ⚠️ V1 only | 特殊規則判斷 |
| **ACT_HI_PROCINST** | ❌ | ❌ | ❌ | 無 Vx 邏輯 |

### 5.3 推薦方案（不使用 ACT_HI_VARINST）

**優先順序**：
```
1️⃣ MDM 主檔表（最準確，包含 Region）
2️⃣ FlowableTaskStats（快速，可能不完整）
3️⃣ 標記為缺失（無法補齊）
```

**Vx 邏輯來源**：
```
1️⃣ FlowableTaskStats（包含 TaskDefinitionKey 和 MoNumber）
2️⃣ ACT_HI_TASKINST（只有 TaskDefinitionKey）
```

---

**分析完成日期**：2026-01-21  
**分析狀態**：✅ 現狀分析完成
