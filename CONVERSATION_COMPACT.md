# 對話摘要 - V1/V3 歸屬邏輯修正

## 問題背景
用戶發現 WJ2+NBU+E5 在 2025-12-28 的數據不符合期望：
- **期望**：V1=3筆, V3=4筆
- **實際**：V1=7筆, V3=0筆

## 根本原因
V1/V3 歸屬邏輯錯誤：所有 315% 工單號都被歸類為 V1，導致 V3 任務被錯誤歸類。

## 解決方案
修正 `scripts/transform_silver_generic_metrics.py` 中的邏輯：
```sql
-- 修正前：所有 315% 工單號都歸 V1
WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%' THEN 'V1'

-- 修正後：只有特定 315% 工單號歸 V1  
WHEN COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
```

## 技術問題解答

### 1. 日期邏輯
**問題**：應該使用什麼日期條件？  
**答案**：使用 OR 條件 `START_TIME OR CLAIM_TIME OR END_TIME`

### 2. CLAIM_TIME = END_TIME
**問題**：這是否正常？  
**答案**：正常。Kafka 來源任務的 CLAIM_TIME 可能為空，完成時等於 END_TIME

### 3. VX 歸屬邏輯
**MSSQL 版本**：
```sql
CASE 
    WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
    WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
    WHEN var_moNumber.TEXT_ IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
    WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
    WHEN var_moNumber.TEXT_ LIKE '196%' OR ... THEN 'V1'
    ELSE LEFT(hti.TASK_DEF_KEY_, 2)
END
```

### 4. 狀態條件
**MSSQL 狀態判斷**：
```sql
-- Done: END_TIME_ IS NOT NULL
-- TODO: END_TIME_ IS NULL AND ASSIGNEE_ IS NULL
-- DOING: END_TIME_ IS NULL AND ASSIGNEE_ IS NOT NULL
```

## 數據同步問題
- **ClickHouse**：有 2025-12-28 資料（11筆）
- **MSSQL**：無 2025-12-28 資料（0筆）
- **結論**：兩個資料源可能不同步，以 ClickHouse 為準

## 修正結果
- **V1 任務數**：從 436,243 筆降至 15,184 筆（減少 421,059 筆錯誤歸類）
- **驗證結果**：WJ2+NBU+E5 2025-12-28 現在是 V1=3筆, V3=4筆 ✅

## 關鍵檔案
- `scripts/transform_silver_generic_metrics.py` - 主要修正檔案
- `scripts/compare_clickhouse_mssql_sync.py` - 數據同步檢查
- `scripts/debug_mssql_date_logic.py` - MSSQL 調試工具
- `docs/metric_definitions.md` - 業務規則定義

## 系統狀態
- ✅ V1/V3 歸屬邏輯已修正
- ✅ 日期邏輯已統一  
- ✅ 狀態條件已標準化
- ✅ 數據驗證通過

---
**完成日期**：2026-01-21  
**狀態**：✅ 問題已解決，邏輯已修正並驗證