# Vx 歸屬邏輯修正方案

**日期**：2026-01-21  
**狀態**：🔴 待修正  
**優先級**：高  

---

## 問題描述

### 現象
驗證結果顯示：工單號規則（196/199/200/210/212/213/315 開頭）的任務**沒有被正確歸類為 V1**。

```
工單號規則任務總數：996,028 筆
  ✅ 被歸類為 V1：4,975 筆 (0.5%)
  ❌ 被歸類為非 V1：991,053 筆 (99.5%)
```

### 根因分析

**Silver 層轉換邏輯中的 CASE 語句順序有誤**：

```sql
-- ❌ 錯誤的邏輯順序
CASE 
    WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1'
    WHEN t.TaskDefinitionKey LIKE 'V2%' THEN 'V2'  -- ⚠️ 先檢查 V2
    WHEN COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
    WHEN t.TaskDefinitionKey LIKE 'V3%' THEN 'V3'  -- ⚠️ 先檢查 V3
    WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' ... THEN 'V1'  -- ⚠️ 工單號規則永遠不會被檢查
    ELSE ...
END
```

**問題**：
- 如果任務的 TaskDefinitionKey 是 'V2%' 或 'V3%'，會立即被歸類為 V2 或 V3
- 工單號規則的檢查永遠不會被執行
- 導致 991,053 筆應該是 V1 的任務被錯誤歸類

---

## 修正方案

### 業務規則澄清

根據 Log 檔案和業務需求：

1. **基本規則**：L5 任務編號（TaskDefinitionKey）開頭決定基本分類
   - 開頭為 'V1' → V1 任務
   - 開頭為 'V2' → V2 任務
   - 開頭為 'V3' → V3 任務

2. **工單號規則**（優先級最高）：工單號 196/199/200/210/212/213/315 開頭
   - **無論 TaskDefinitionKey 是什麼**（V1/V2/V3），都歸類為 **V1**
   - 這包括「V1 調用 V3 流程所產生的任務」（TaskDefinitionKey 是 V3，但工單號符合規則）

### 正確的邏輯順序

**優先級**（從高到低）：
1. **工單號規則**（最高優先級）- 無論 TaskDefinitionKey 是什麼
2. **TaskDefinitionKey 前綴**（次優先級）

```sql
-- ✅ 正確的邏輯順序
CASE 
    -- 優先級 1：工單號規則（最高，覆蓋所有 TaskDefinitionKey）
    WHEN COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
    WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
    THEN 'V1'
    
    -- 優先級 2：TaskDefinitionKey 前綴（當工單號規則不符合時）
    WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1'
    WHEN t.TaskDefinitionKey LIKE 'V2%' THEN 'V2'
    WHEN t.TaskDefinitionKey LIKE 'V3%' THEN 'V3'
    
    -- 預設值
    ELSE COALESCE(substring(t.TaskDefinitionKey, 1, 2), 'Unknown')
END
```

### 業務場景示例

| TaskDefinitionKey | 工單號 | 結果 | 說明 |
|------------------|--------|------|------|
| V1_XXX | 196XXXX | **V1** | 工單號規則優先 |
| V2_XXX | 199XXXX | **V1** | 工單號規則優先（V1 調用 V3 流程的情況） |
| V3_XXX | 200XXXX | **V1** | 工單號規則優先（V1 調用 V3 流程的情況） |
| V1_XXX | 300XXXX | **V1** | TaskDefinitionKey 規則 |
| V2_XXX | 300XXXX | **V2** | TaskDefinitionKey 規則 |
| V3_XXX | 300XXXX | **V3** | TaskDefinitionKey 規則 |

### V1 子類型邏輯

修正後，V1 子類型邏輯應該是：

```sql
CASE 
    -- 工單號規則的 V1 任務（無論原始 TaskDefinitionKey 是什麼）
    WHEN (COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037')
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%')
         AND p.BUSINESS_KEY_ LIKE '%NPE%'
    THEN 'V1_NPE'
    
    WHEN (COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037')
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
          OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%')
    THEN 'V1_MFG'
    
    -- TaskDefinitionKey 的 V1 任務（工單號規則不符合時）
    WHEN t.TaskDefinitionKey LIKE 'V1%' AND p.BUSINESS_KEY_ LIKE '%NPE%'
    THEN 'V1_NPE'
    
    WHEN t.TaskDefinitionKey LIKE 'V1%'
    THEN 'V1_MFG'
    
    -- 其他情況（V2/V3 等）
    ELSE NULL
END
```

---

## 修正步驟

### Step 1：修正 Silver 層轉換邏輯

**檔案**：`scripts/transform_silver_generic_metrics.py`

**修改位置**：TRANSFORM_FACT_TASK_VX_SQL 中的 vx_type CASE 語句

**修改內容**：
- 將工單號規則檢查移到最前面（優先級最高）
- 將 TaskDefinitionKey 檢查移到後面（優先級次高）

### Step 2：重新轉換 Silver 層資料

```bash
python scripts/transform_silver_generic_metrics.py --table task
```

### Step 3：驗證修正結果

```bash
python scripts/validate_vx_subtype_logic.py
```

**預期結果**：
- 所有工單號規則任務都被歸類為 V1
- V1_NPE + V1_MFG = V1 總數

---

## 影響範圍

### 受影響的表
- `silver.FACT_TASK_VX_ATTRIBUTION`（vx_type 和 vx_subtype 欄位）
- `gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT`（需要重新聚合）

### 受影響的指標
- L5 任務執行完成率（按 Vx 類型分類）
- V1_NPE 任務數
- V1_MFG 任務數

### 資料量變化預估
- V1 任務數：從 ~15,000 筆 增加到 ~1,000,000 筆
- V2/V3 任務數：相應減少

---

## 修正前後對比

### 修正前
```
工單號規則任務：996,028 筆
  V1：4,975 筆 (0.5%)
  V2：13,482 筆 (1.35%)
  V3：488,059 筆 (49.0%)
  其他：489,512 筆 (49.15%)
```

### 修正後（預期）
```
工單號規則任務：996,028 筆
  V1：996,028 筆 (100%)
    V1_NPE：? 筆
    V1_MFG：? 筆
```

---

## 驗證清單

- [ ] 修正 `scripts/transform_silver_generic_metrics.py` 中的 Vx 歸屬邏輯
- [ ] 執行 `python scripts/transform_silver_generic_metrics.py --table task`
- [ ] 執行 `python scripts/validate_vx_subtype_logic.py` 驗證修正結果
- [ ] 檢查 V1_NPE 和 V1_MFG 的分布是否合理
- [ ] 重新生成 Gold 層快照
- [ ] 驗證 Cube.js 中的 L5 指標是否正確更新

---

**修正狀態**：🔴 待執行  
**預計完成時間**：2026-01-21  
**負責人**：待指派  

