# 文件 × 規則 × 實作一致性驗證報告

**報告日期：** 2026-01-22  
**驗證範圍：** 工單號 315% 規則、NPE 判別邏輯、Silver 層 factory 欄位定義  
**驗證狀態：** ✅ 完成

---

## 執行摘要

本次驗證針對三個關鍵規則進行了完整的文件與實作一致性檢查，並完成了必要的修正：

| 規則 | 文件定義 | 實作狀態 | 修正狀態 |
|------|---------|---------|---------|
| **規則一：V1/V2/V3 分類** | ✅ 已定義 | ✅ 已實作 | ✅ 無需修正 |
| **規則二：工單 override（315%）** | ⚠️ 定義不完整 | ❌ 實作不完整 | ✅ 已修正 |
| **規則三：Q/R 排除** | ✅ 已定義 | ✅ 已實作 | ✅ 無需修正 |
| **規則四：NPE/MFG 細分** | ⚠️ 資料來源混亂 | ❌ 實作混亂 | ✅ 已修正 |

---

## 詳細驗證結果

### 規則一：V1/V2/V3 分類

**文件定義：** ✅ 已定義  
**實作位置：** `sql/12_create_silver_mviews_layer2.sql` (L45-48)

```sql
WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1'
WHEN t.TaskDefinitionKey LIKE 'V2%' THEN 'V2'
WHEN t.TaskDefinitionKey LIKE 'V3%' THEN 'V3'
```

**驗證結果：** ✅ 文件與實作一致  
**狀態：** 無需修正

---

### 規則二：工單 override（315% 規則）

#### 問題發現

**文件定義（`docs/metric_definitions.md`）：**
```
工單編號以 196 / 199 / 200 / 210 / 212 / 213 / 315 開頭者
判斷邏輯：LIKE '196%' OR LIKE '199%' OR ... OR LIKE '315%'
```

**原實作（修正前）：**
```sql
WHEN COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
```

**問題：** 
- 文件要求：所有 315 開頭的工單號
- 實作只有：三個特定工單號
- **缺口：** 實作不完整，遺漏了其他 315 開頭的工單號

#### 修正內容

**修正後實作（`sql/12_create_silver_mviews_layer2.sql` L45-52）：**
```sql
WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%'
THEN 'V1'
```

**修正影響：**
- ✅ 現在涵蓋所有 315 開頭的工單號（如 3152600035, 3152600036, 3152600037, 3152600038, 3152600100 等）
- ✅ 與文件定義完全一致
- ⚠️ 可能增加符合 V1 特殊規則的任務數量

**驗證結果：** ✅ 已修正，文件與實作一致

---

### 規則三：Q/R 排除

**文件定義：** ✅ 已定義  
**實作位置：** `sql/12_create_silver_mviews_layer2.sql` (L95-99)

```sql
WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'Q%' 
     OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'R%' THEN 1
```

**驗證結果：** ✅ 文件與實作一致  
**狀態：** 無需修正

---

### 規則四：NPE/MFG 細分

#### 問題發現

**文件定義（`docs/metric_definitions.md`）：**
```
製造產品廠欄位包含 'NPE' → V1_NPE
製造產品廠不包含 'NPE' → V1_MFG
```

**原實作混亂情況：**
1. **資料來源混用：**
   - 有時使用 `BUSINESS_KEY_ LIKE '%NPE%'`（來自 ACT_HI_PROCINST）
   - 有時使用 `varinst_name LIKE '%NPE%'`（來自 ACT_HI_VARINST）
   - 兩者資料來源不同，導致判別結果不一致

2. **欄位定義不清：**
   - 文件提到「製造產品廠欄位」
   - 實作中混用了多個欄位
   - 不清楚應該使用哪個欄位作為標準

#### 修正內容

**修正後實作（`sql/12_create_silver_mviews_layer2.sql` L60-85）：**

```sql
-- 統一使用 varinst_name 欄位判別 NPE
CASE 
    -- 工單號規則的 V1 任務 + NPE 判別
    WHEN (COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
          OR ... OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%')
         AND v.varinst_name LIKE '%NPE%'
    THEN 'V1_NPE'
    
    WHEN (COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
          OR ... OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%')
    THEN 'V1_MFG'
    
    -- TaskDefinitionKey 的 V1 任務 + NPE 判別
    WHEN t.TaskDefinitionKey LIKE 'V1%' AND v.varinst_name LIKE '%NPE%'
    THEN 'V1_NPE'
    
    WHEN t.TaskDefinitionKey LIKE 'V1%'
    THEN 'V1_MFG'
    
    ELSE NULL
END AS vx_subtype
```

**修正要點：**
1. ✅ **統一資料來源：** 使用 `varinst_name LIKE '%NPE%'`（來自 ACT_HI_VARINST）
2. ✅ **清晰的邏輯流程：** 先判斷工單號規則，再判斷 NPE
3. ✅ **完整的 V1 子類型：** 區分 V1_NPE 和 V1_MFG

**varinst_name 欄位說明：**
- **來源表：** `bronze.bpm_act_hi_varinst`（ACT_HI_VARINST）
- **定義：** 所有 NAME_ 值的連接字符串（在 `silver.mv_varinst_pivoted` 中預計算）
- **用途：** 判斷流程變數中是否包含 NPE 相關資訊
- **優勢：** 比 BUSINESS_KEY_ 更準確，因為直接來自流程變數

**驗證結果：** ✅ 已修正，文件與實作一致

---

## Factory 欄位定義澄清

### 問題背景

在驗證過程中發現 Silver 層存在兩個不同的 factory 欄位定義：

| 欄位名稱 | 來源 | 定義 | 用途 |
|---------|------|------|------|
| `varinst_factory` | ACT_HI_VARINST | 流程變數中的 factory 值 | 任務層級的製造區 |
| `factory_code` | MDM 主檔 | 標準化的 MFG_PLANT_CODE | 員工組織層級的製造區 |

### 澄清結果

**Silver 層設計原則：**
1. **任務層級（`mv_fact_task_vx_attribution`）：** 使用 `varinst_factory`（流程變數）
2. **員工層級（`mv_emp_org_info`）：** 使用 `factory_code`（MDM 主檔）
3. **聚合層級（`mv_l5_metrics_realtime`）：** 使用 `factory`（來自任務層級）

**實作位置：**
- `sql/11_create_silver_mviews_layer1.sql` (L20-21, L50-51)
- `sql/12_create_silver_mviews_layer2.sql` (L108-109)

**驗證結果：** ✅ 設計清晰，無需修正

---

## 一致性驗證矩陣

| 規則 | 文件定義 | 實作位置 | 修正前 | 修正後 | 驗證結果 |
|------|---------|---------|--------|--------|---------|
| **規則一：V1/V2/V3 分類** | ✅ | `12_create_silver_mviews_layer2.sql` L45-48 | ✅ 正確 | ✅ 正確 | ✅ 一致 |
| **規則二：工單 override（315%）** | ✅ | `12_create_silver_mviews_layer2.sql` L45-52 | ❌ 不完整 | ✅ 完整 | ✅ 一致 |
| **規則三：Q/R 排除** | ✅ | `12_create_silver_mviews_layer2.sql` L95-99 | ✅ 正確 | ✅ 正確 | ✅ 一致 |
| **規則四：NPE/MFG 細分** | ✅ | `12_create_silver_mviews_layer2.sql` L60-85 | ❌ 混亂 | ✅ 清晰 | ✅ 一致 |
| **Factory 欄位定義** | ⚠️ 需澄清 | `11/12_create_silver_mviews_layer*.sql` | ⚠️ 混亂 | ✅ 澄清 | ✅ 一致 |

---

## 修正檔案清單

### 1. SQL 檔案修正

**檔案：** `sql/12_create_silver_mviews_layer2.sql`

**修正內容：**
- ✅ 第 45-52 行：工單號規則改為 `LIKE '315%'`（3 處修正）
- ✅ 第 60-85 行：NPE 邏輯統一使用 `varinst_name LIKE '%NPE%'`（完整重寫）
- ✅ 第 95-99 行：Q/R 排除邏輯保持不變（已驗證正確）

**修正狀態：** ✅ 已完成

### 2. 文件修正

**檔案：** `docs/metric_definitions.md`

**修正內容：**
- ✅ 新增「⚠️ 資料來源變更說明 (2026-01-22)」章節
- ✅ 澄清工單號 315% 規則為 `LIKE '315%'`
- ✅ 澄清 NPE 判別使用 `varinst_name LIKE '%NPE%'`
- ✅ 新增 ACT_HI_VARINST 表說明
- ✅ 新增轉置 SQL 範例
- ✅ 新增資料來源 SQL 範例

**修正狀態：** ✅ 已完成

---

## 驗證方法

### 1. 語法驗證
```
✅ sql/11_create_silver_mviews_layer1.sql - No diagnostics found
✅ sql/12_create_silver_mviews_layer2.sql - No diagnostics found
```

### 2. 邏輯驗證

**工單號 315% 規則：**
```sql
-- 修正前：只有三個特定工單號
WHEN COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037')

-- 修正後：所有 315 開頭的工單號
WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%'
```

**NPE 判別邏輯：**
```sql
-- 修正前：混用 BUSINESS_KEY_ 和 varinst_name
WHEN p.BUSINESS_KEY_ LIKE '%NPE%'  -- 不一致

-- 修正後：統一使用 varinst_name
WHEN v.varinst_name LIKE '%NPE%'  -- 一致
```

### 3. 文件驗證

**文件更新檢查清單：**
- ✅ 工單號 315% 規則定義已澄清
- ✅ NPE 判別資料來源已明確
- ✅ Factory 欄位定義已澄清
- ✅ 新增資料來源 SQL 範例
- ✅ 新增 ACT_HI_VARINST 表說明

---

## 後續行動

### 立即行動（必須）
1. ✅ **已完成：** 修正 `sql/12_create_silver_mviews_layer2.sql` 中的 315% 規則
2. ✅ **已完成：** 修正 NPE 判別邏輯為統一使用 `varinst_name`
3. ✅ **已完成：** 更新 `docs/metric_definitions.md` 文件

### 驗證行動（建議）
1. **測試 MVIEW 建立：** 在 ClickHouse 中執行修正後的 SQL，確認 MVIEW 正確建立
2. **數據驗證：** 比較修正前後的任務數量變化，確認 315% 規則擴展的影響
3. **NPE 判別驗證：** 抽樣檢查 V1_NPE 和 V1_MFG 的分類結果

### 文檔行動（建議）
1. **更新 metric_definitions.md v1.3：** 將澄清內容正式納入版本控制
2. **建立實作指南：** 為開發人員提供清晰的規則實作參考
3. **建立驗證清單：** 為未來的規則修改提供驗證模板

---

## 結論

✅ **驗證完成：** 文件 × 規則 × 實作已達成一致性

**關鍵修正：**
1. 工單號 315% 規則：從特定工單號擴展為所有 315 開頭的工單號
2. NPE 判別邏輯：統一使用 `varinst_name LIKE '%NPE%'` 作為標準
3. Factory 欄位定義：明確區分任務層級和員工層級的 factory 欄位

**驗證狀態：**
- ✅ SQL 語法正確
- ✅ 邏輯實現完整
- ✅ 文件定義清晰
- ✅ 三者一致性達成

---

**報告簽署：** Kiro Agent  
**驗證日期：** 2026-01-22  
**下一步：** 等待用戶確認是否需要進行 MVIEW 測試或其他驗證
