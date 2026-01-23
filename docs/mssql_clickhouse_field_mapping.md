# MSSQL → ClickHouse 欄位對應表

## 概述
此文件記錄 MSSQL Reference Query 與 ClickHouse 各層之間的欄位對應關係，用於資料一致性驗證和問題診斷。

## 完整欄位對應表

| MSSQL 欄位 | ClickHouse Bronze | ClickHouse Silver | ClickHouse Gold | 資料型別 | 轉換邏輯 | 問題狀態 |
|------------|-------------------|-------------------|-----------------|----------|----------|----------|
| processInstanceId | PROC_INST_ID_ | proc_inst_id | - | String | 直接對應 | ✅ 正常 |
| processDefinitionKey | KEY_ (from procdef) | - | - | String | JOIN 取得 | ✅ 正常 |
| processDefinitionName | NAME_ (from procdef) | - | - | String | JOIN 取得 | ✅ 正常 |
| plant | TEXT_ (varinst plant) | plant | plant_code | String | EAV 轉置 | ✅ 正常 |
| factory | TEXT_ (varinst factory) | factory | factory_code | String | EAV 轉置 | ✅ 正常 |
| productionArea | TEXT_ (varinst productionArea) | - | - | String | EAV 轉置 | ✅ 正常 |
| line | TEXT_ (varinst lineName) | line | line_code | String | EAV 轉置 | ✅ 正常 |
| modelName | TEXT_ (varinst modelName) | - | - | String | EAV 轉置 | ✅ 正常 |
| deliveryArea | TEXT_ (varinst deliveryArea) | - | - | String | EAV 轉置 | ✅ 正常 |
| scheduleNumber | TEXT_ (varinst scheduleNumber) | - | - | String | EAV 轉置 | ✅ 正常 |
| moNumber | TEXT_ (varinst moNumber) | mo_number | - | String | EAV 轉置 | ✅ 正常 |
| sapPlant | TEXT_ (varinst sapPlant) | - | - | String | EAV 轉置 | ✅ 正常 |
| sapProductGroup | TEXT_ (varinst sapProductGroup) | - | - | String | EAV 轉置 | ✅ 正常 |
| pallet | TEXT_ (varinst pallet) | - | - | String | EAV 轉置 | ✅ 正常 |
| transferNo | TEXT_ (varinst transferNo) | - | - | String | EAV 轉置 | ✅ 正常 |
| qBlockEventId | TEXT_ (varinst qBlockEventId) | - | - | String | EAV 轉置 | ✅ 正常 |
| defectSn | TEXT_ (varinst defectSn) | - | - | String | EAV 轉置 | ✅ 正常 |
| timeKey | CONCAT('_', TEXT_) | - | - | String | EAV 轉置 + 前綴 | ⚠️ NULL 處理問題 |
| taskId | ID_ | task_id | - | String | 直接對應 | ✅ 正常 |
| taskDefinitionKey | TASK_DEF_KEY_ | task_definition_key | - | String | 直接對應 | ✅ 正常 |
| taskName | NAME_ | task_name | - | String | 直接對應 | ✅ 正常 |
| taskStatus | CASE WHEN... | task_status | - | String | 狀態邏輯轉換 | ✅ 正常 |
| taskBypass | CASE WHEN LONG_=1 | task_bypass | - | String | autoComplete 變數 | ✅ 正常 |
| taskAssignee | ASSIGNEE_ | task_assignee_account | - | String | 直接對應 | ✅ 正常 |
| taskAssigneeAccount | ADAccount (HR_Employee) | - | - | String | JOIN 取得 | ✅ 正常 |
| taskAssigneeName | EmpName (HR_Employee) | task_assignee_name | - | String | JOIN 取得 | ✅ 正常 |
| taskCreateTime | START_TIME_ | task_create_time | snapshot_date | DateTime/String | 格式轉換 | ⚠️ 精度差異 |
| taskClaimTime | CLAIM_TIME_ | task_claim_time | - | DateTime/String | 格式轉換 | ⚠️ 精度差異 |
| taskEndTime | END_TIME_ | task_end_time | - | DateTime/String | 格式轉換 | ⚠️ 精度差異 |
| taskDurationMinutes | DATEDIFF 計算 | 計算欄位 | - | Float64 | 時間差計算 | ⚠️ 計算差異 |
| taskWorkMinutes | DATEDIFF 計算 | 計算欄位 | - | Float64 | 時間差計算 | ⚠️ 計算差異 |
| deleteReason | DELETE_REASON_ | - | - | String | 直接對應 | ✅ 正常 |
| - | - | vx_type | vx_type | String | 業務邏輯計算 | ❌ Silver 層膨脹 |
| - | - | vx_subtype | vx_subtype | String | 業務邏輯計算 | ❌ Silver 層膨脹 |
| - | - | is_excluded | - | Int | 排除邏輯 | ❌ Silver 層膨脹 |
| - | - | exclude_reason | - | String | 排除原因 | ❌ Silver 層膨脹 |

## 問題詳細分析

### ✅ 正常欄位 (Bronze 層)
這些欄位在 Bronze 層與 MSSQL 基本一致，沒有重大問題：
- 所有基礎識別欄位 (processInstanceId, taskId 等)
- 所有流程變數 (plant, factory, line 等)
- 基礎任務屬性 (taskStatus, taskBypass 等)

### ⚠️ 有問題的欄位

#### 1. timeKey
- **MSSQL**: `CONCAT('_', var_time.TEXT_)` → 結果: `'_'`
- **ClickHouse**: `concat('_', v_time.TEXT_)` → 結果: `'NULL'`
- **問題**: ClickHouse 的 `concat` 函數對 NULL 值處理不同
- **修正**: 使用 `COALESCE(v_time.TEXT_, '')` 或 `CASE WHEN` 邏輯

#### 2. taskCreateTime (時間精度)
- **MSSQL**: `'2025-12-25 08:00:01'`
- **ClickHouse**: `'2025-12-25 08:00:01.573'`
- **問題**: ClickHouse 保留毫秒精度，MSSQL 截斷到秒
- **影響**: 字串比對會失敗，但功能上無影響

#### 3. taskDurationMinutes (計算差異)
- **MSSQL**: `42308.92`
- **ClickHouse**: `41828.92`
- **問題**: 計算基準時間不同 (MSSQL 用 GETDATE()，ClickHouse 用 now())
- **影響**: 實時計算會有時間差

### ❌ 嚴重問題的欄位 (Silver 層)

#### Silver 層資料膨脹問題
所有 Silver 層的業務邏輯欄位都受到影響：
- `vx_type`, `vx_subtype`: 業務分類邏輯
- `is_excluded`, `exclude_reason`: 排除邏輯
- **根本原因**: `mv_fact_task_vx_attribution` MVIEW 的 JOIN 邏輯錯誤

## EAV 轉置邏輯分析

### MSSQL EAV 查詢模式
```sql
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant 
    on hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ 
    and var_plant.NAME_ = 'plant'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory 
    on hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ 
    and var_factory.NAME_ = 'factory'
-- ... 每個變數一個 LEFT JOIN
```

### ClickHouse EAV 轉置 (Bronze 層)
```sql
LEFT JOIN bronze.bpm_act_hi_varinst v_plant 
    ON p.PROC_INST_ID_ = v_plant.PROC_INST_ID_ AND v_plant.NAME_ = 'plant'
LEFT JOIN bronze.bpm_act_hi_varinst v_factory 
    ON p.PROC_INST_ID_ = v_factory.PROC_INST_ID_ AND v_factory.NAME_ = 'factory'
-- ... 每個變數一個 LEFT JOIN
```

### ClickHouse EAV 轉置 (Silver MVIEW)
```sql
-- mv_varinst_pivoted
SELECT 
    PROC_INST_ID_,
    MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS varinst_plant,
    MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS varinst_factory,
    -- ...
FROM bronze.bpm_act_hi_varinst
GROUP BY PROC_INST_ID_
```

**分析**: Silver 層的 EAV 轉置邏輯本身是正確的，問題在於後續的 JOIN。

## JOIN 邏輯分析

### 問題 MVIEW: `mv_fact_task_vx_attribution`

```sql
FROM bronze.bpm_act_hi_taskinst t
LEFT JOIN bronze.bmp_act_hi_procinst p 
    ON t.PROC_INST_ID_ = p.PROC_INST_ID_                    -- 1:1 關係 ✅
LEFT JOIN silver.mv_varinst_pivoted v
    ON t.PROC_INST_ID_ = v.PROC_INST_ID_                    -- 可能 1:N 關係 ❌
LEFT JOIN bronze.common_hr_employee he
    ON t.ASSIGNEE_ = he.EmpCode                             -- 可能 1:N 關係 ❌
LEFT JOIN bronze.bpm_act_hi_varinst tb
    ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'    -- 1:1 關係 ✅
```

**可能的問題點**:
1. `mv_varinst_pivoted` 可能有重複的 `PROC_INST_ID_`
2. `common_hr_employee` 可能有重複的 `EmpCode`
3. 日期過濾條件可能在錯誤的位置

## 診斷查詢

### 檢查 mv_varinst_pivoted 重複
```sql
SELECT 
    PROC_INST_ID_, 
    COUNT(*) as cnt
FROM silver.mv_varinst_pivoted 
WHERE PROC_INST_ID_ IN (
    'a83fa1af-e124-11f0-8766-badd3bc212ac',
    'a8c8a825-e124-11f0-8766-badd3bc212ac',
    'a9607bab-e124-11f0-8766-badd3bc212ac',
    'dc9cab8e-e155-11f0-8766-badd3bc212ac',
    '1178d911-e0aa-11f0-8766-badd3bc212ac'
)
GROUP BY PROC_INST_ID_ 
HAVING COUNT(*) > 1;
```

### 檢查 common_hr_employee 重複
```sql
SELECT 
    EmpCode, 
    COUNT(*) as cnt
FROM bronze.common_hr_employee 
WHERE EmpCode IN ('56629210', '', NULL)
GROUP BY EmpCode 
HAVING COUNT(*) > 1;
```

### 檢查 Silver MVIEW 重複
```sql
SELECT 
    task_id, 
    COUNT(*) as cnt
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE task_id IN (
    '117c3488-e0aa-11f0-8766-badd3bc212ac',
    'a84b6195-e124-11f0-8766-badd3bc212ac',
    'a8cf860b-e124-11f0-8766-badd3bc212ac',
    'a96360f1-e124-11f0-8766-badd3bc212ac',
    'dc9fb8e2-e155-11f0-8766-badd3bc212ac'
)
GROUP BY task_id 
HAVING COUNT(*) > 1;
```

## 修正建議

### 立即修正 (Bronze 層)
```sql
-- 修正 timeKey 的 NULL 處理
COALESCE(CONCAT('_', v_time.TEXT_), '_') as timeKey
```

### 立即修正 (Silver 層)
```sql
-- 在 mv_fact_task_vx_attribution 中加入去重邏輯
SELECT DISTINCT
    t.ID_ AS task_id,
    -- ... 其他欄位
FROM bronze.bpm_act_hi_taskinst t
-- ... JOIN 邏輯保持不變
```

### 長期改善
1. 建立資料品質監控，自動檢測記錄數異常
2. 在所有 MVIEW 中加入 `FINAL` 關鍵字
3. 定期重建 MVIEW 以避免累積錯誤
4. 建立標準的欄位對應測試套件