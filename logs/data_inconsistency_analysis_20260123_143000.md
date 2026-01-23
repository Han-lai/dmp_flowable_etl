# MSSQL vs ClickHouse 資料不一致分析報告

## 分析條件
- 日期: 2025-12-25
- 條件: plant='WJ2', factory='NBU', line='E5'
- 分析時間: 2026-01-23 14:30:00

## 1. 記錄數量統計

| 資料層 | 記錄數 | 說明 |
|--------|--------|------|
| MSSQL Reference | 5 | 正確基準 |
| ClickHouse Bronze | 5 | 原始同步層 |
| ClickHouse Silver | 188 | 轉換邏輯層 |
| ClickHouse Gold | 0 | 聚合指標層 |

## 2. 關鍵發現

### 🚨 嚴重問題：Silver 層資料異常膨脹
- **MSSQL Reference**: 5 筆任務記錄
- **ClickHouse Bronze**: 5 筆任務記錄 ✅ 
- **ClickHouse Silver**: 188 筆任務記錄 ❌ (膨脹 37.6 倍)
- **ClickHouse Gold**: 0 筆聚合記錄 ❌ (完全遺失)

### 🔍 Bronze 層分析
✅ **Bronze 層資料完整**: 記錄數與 MSSQL 一致 (5 筆)
⚠️ **欄位值差異**:
- `timeKey`: MSSQL='_' vs Bronze='NULL' (EAV 轉置問題)
- `taskCreateTime`: 精度差異 (MSSQL: '2025-12-25 08:00:01' vs Bronze: '2025-12-25 08:00:01.573')
- `taskDurationMinutes`: 計算差異 (MSSQL: 42308.92 vs Bronze: 41828.92)

### 🔍 Silver 層分析
❌ **嚴重的資料膨脹**: 5 筆 Bronze 記錄變成 188 筆 Silver 記錄
- 可能原因：MVIEW 的 JOIN 邏輯錯誤，產生笛卡爾積
- 影響：後續 Gold 層聚合失效

### 🔍 Gold 層分析
❌ **完全無資料**: 0 筆聚合記錄
- 可能原因：Silver 層資料異常導致聚合條件失效
- 影響：最終指標完全錯誤

## 3. 根本原因分析

### Bronze 層問題
1. **EAV 轉置邏輯不完整**: `timeKey` 欄位未正確處理 NULL 值
2. **時間精度不一致**: DateTime 格式轉換導致精度差異
3. **計算邏輯差異**: `taskDurationMinutes` 計算方式與 MSSQL 不同

### Silver 層問題（最嚴重）
1. **MVIEW JOIN 邏輯錯誤**: 
   - `mv_fact_task_vx_attribution` 的 JOIN 條件可能產生笛卡爾積
   - 特別是與 `mv_varinst_pivoted` 的 JOIN
2. **過濾條件不當**: 
   - 日期過濾條件可能過於寬鬆
   - Plant/Factory/Line 過濾可能在錯誤的層級
3. **重複資料**: MVIEW 可能包含重複的任務記錄

### Gold 層問題
1. **依賴 Silver 層**: Silver 層資料異常直接影響 Gold 層
2. **聚合條件過嚴**: 可能因為 Silver 層資料格式問題導致聚合失效

## 4. 詳細技術分析

### Silver MVIEW 問題診斷

根據 `sql/12_create_silver_mviews_layer2.sql` 的邏輯：

```sql
-- 問題可能出現在這個 MVIEW
CREATE MATERIALIZED VIEW silver.mv_fact_task_vx_attribution
...
FROM bronze.bpm_act_hi_taskinst t
LEFT JOIN bronze.bpm_act_hi_procinst p 
    ON t.PROC_INST_ID_ = p.PROC_INST_ID_
LEFT JOIN silver.mv_varinst_pivoted v
    ON t.PROC_INST_ID_ = v.PROC_INST_ID_  -- 可能的問題點
LEFT JOIN bronze.common_hr_employee he
    ON t.ASSIGNEE_ = he.EmpCode
LEFT JOIN bronze.bpm_act_hi_varinst tb
    ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
```

**可能問題**:
1. `mv_varinst_pivoted` 可能包含重複的 `PROC_INST_ID_`
2. `common_hr_employee` JOIN 可能產生多筆記錄
3. 日期過濾條件在 MVIEW 中可能不正確

### EAV 轉置問題

`mv_varinst_pivoted` 的邏輯：
```sql
SELECT 
    PROC_INST_ID_,
    MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber,
    ...
    arrayStringConcat(arrayDistinct(groupArray(NAME_)), ',') AS varinst_name
FROM bronze.bmp_act_hi_varinst
GROUP BY PROC_INST_ID_
```

**可能問題**: 
- `GROUP BY PROC_INST_ID_` 可能產生重複記錄
- `arrayStringConcat` 邏輯可能導致 JOIN 異常

## 5. 立即修正方案

### 優先級 1: 修正 Silver 層資料膨脹
```sql
-- 檢查 mv_varinst_pivoted 是否有重複
SELECT PROC_INST_ID_, COUNT(*) as cnt
FROM silver.mv_varinst_pivoted 
GROUP BY PROC_INST_ID_ 
HAVING COUNT(*) > 1;

-- 檢查 Silver MVIEW 的重複記錄
SELECT task_id, COUNT(*) as cnt
FROM silver.mv_fact_task_vx_attribution FINAL
WHERE toDate(task_create_time) = '2025-12-25'
AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
GROUP BY task_id
HAVING COUNT(*) > 1;
```

### 優先級 2: 修正 Bronze 層欄位問題
```sql
-- 修正 timeKey 的 NULL 處理
-- 在 Bronze 同步時確保 CONCAT('_', TEXT_) 正確處理 NULL
```

### 優先級 3: 重建 MVIEW
```sql
-- 重建有問題的 MVIEW
DROP TABLE silver.mv_fact_task_vx_attribution;
-- 重新執行建立腳本，並加入去重邏輯
```

## 6. 建議的修正步驟

### 第一步：診斷 Silver 層問題
1. 檢查 `mv_varinst_pivoted` 是否有重複的 `PROC_INST_ID_`
2. 檢查 `mv_fact_task_vx_attribution` 的 JOIN 邏輯
3. 確認日期過濾條件是否正確

### 第二步：修正 MVIEW 邏輯
1. 在 `mv_fact_task_vx_attribution` 中加入 `DISTINCT` 或適當的去重邏輯
2. 檢查所有 LEFT JOIN 的條件是否會產生笛卡爾積
3. 確保日期過濾在正確的位置

### 第三步：重建並驗證
1. 重建 Silver 層 MVIEW
2. 驗證記錄數是否正確 (應該是 5 筆)
3. 重建 Gold 層 MVIEW
4. 驗證最終聚合結果

## 7. 長期改善建議

### 資料品質監控
1. 建立每日資料一致性檢查
2. 監控各層記錄數變化
3. 自動告警異常資料膨脹

### MVIEW 設計改善
1. 在所有 MVIEW 中加入資料完整性檢查
2. 使用 `FINAL` 關鍵字確保資料一致性
3. 定期重建 MVIEW 以避免累積錯誤

### 測試覆蓋
1. 建立端到端資料驗證測試
2. 每次 MVIEW 變更後執行完整驗證
3. 建立標準的資料品質指標

## 8. 結論

**主要問題**: Silver 層 MVIEW 的 JOIN 邏輯錯誤導致資料膨脹 37.6 倍，進而影響 Gold 層聚合失效。

**緊急修正**: 需要立即檢查並修正 `silver.mv_fact_task_vx_attribution` 的 JOIN 邏輯。

**影響範圍**: 所有依賴 Silver/Gold 層的指標和報表都會受到影響。

**修正時程**: 建議在 24 小時內完成 Silver 層修正，48 小時內完成完整驗證。