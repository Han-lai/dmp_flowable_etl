# ClickHouse MView 工作流驗證報告

**報告日期：** 2026-01-22  
**驗證範圍：** bronze, silver, gold schemas  
**時間範圍：** 2025-12-25 ~ 2025-12-31  
**驗證狀態：** ⚠️ 發現重大問題

---

## 執行摘要

### 🚨 關鍵發現

| 項目 | 狀態 | 嚴重性 |
|------|------|--------|
| **MView 定義更新** | ❌ 部分未更新 | 🔴 高 |
| **315% 規則** | ❌ 仍使用舊規則 | 🔴 高 |
| **NPE 判別邏輯** | ✅ 已更新 | 🟢 低 |
| **MView 資料填充** | ❌ 未填充 | 🔴 高 |
| **MView 運作狀態** | ❌ 未運作 | 🔴 高 |

---

## (1) 所有 Materialized View 清單

### 📊 Schema: gold (1 個 MView)

| 名稱 | 引擎 | 建立時間 | 狀態 |
|------|------|---------|------|
| DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV | ReplacingMergeTree | 2026-01-20 08:35:03 | ⚠️ 無資料 |

### 📊 Schema: silver (11 個 MView)

| 名稱 | 引擎 | 建立時間 | 狀態 |
|------|------|---------|------|
| mv_varinst_pivoted | ReplacingMergeTree | 2026-01-21 09:14:02 | ⚠️ 無資料 |
| mv_emp_user_groups | ReplacingMergeTree | 2026-01-21 09:14:03 | ⚠️ 無資料 |
| mv_emp_node_codes | ReplacingMergeTree | 2026-01-21 09:14:03 | ⚠️ 無資料 |
| mv_emp_org_info | ReplacingMergeTree | 2026-01-21 09:14:03 | ⚠️ 無資料 |
| mv_fact_task_vx_attribution | ReplacingMergeTree | 2026-01-21 09:14:03 | ⚠️ 無資料 |
| mv_task_status_summary | SummingMergeTree | 2026-01-21 09:14:03 | ⚠️ 無資料 |
| mv_l5_metrics_realtime | SummingMergeTree | 2026-01-21 09:14:11 | ⚠️ 無資料 |
| mv_dim_config_user | ReplacingMergeTree | 2026-01-21 09:14:11 | ⚠️ 無資料 |
| vw_fact_task_vx_attribution_realtime | View | 2026-01-21 09:14:11 | ✅ 有資料 (1,300,963 行) |
| vw_fact_task_with_five_level | View | 2026-01-21 07:22:26 | ✅ 有資料 (1,300,963 行) |
| vw_l5_metrics_five_level | View | 2026-01-21 07:22:26 | ✅ 有資料 (8,475 行) |

---

## (2) MView 定義驗證 - 新版工作流檢查

### 🔍 版本分布

| 版本 | 數量 | MView 名稱 |
|------|------|-----------|
| 新版工作流 | 2 | mv_varinst_pivoted, mv_emp_org_info |
| 舊版工作流 | 0 | - |
| 混合版本 | 1 | **mv_fact_task_vx_attribution** ⚠️ |
| 無法判斷 | 9 | 其他 |

### 🚨 關鍵問題：mv_fact_task_vx_attribution

**問題描述：** 該 MView 使用了混合版本的邏輯

**DDL 分析結果：**

```
✅ 新版特徵：
  - 有 varinst_name 欄位
  - 使用 mv_varinst_pivoted
  - 有 NPE 判別邏輯 (varinst_name LIKE '%NPE%')

❌ 舊版特徵：
  - 仍使用舊 315% 規則: IN ('3152600035', '3152600036', '3152600037')
  - 應該改為: LIKE '315%'
```

**實際 DDL 片段：**

```sql
multiIf(
    coalesce(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037'), 'V1',
    (coalesce(v.varinst_moNumber, t.MoNumber) LIKE '196%') OR 
    (coalesce(v.varinst_moNumber, t.MoNumber) LIKE '199%') OR 
    ...
)
```

**預期 DDL 片段：**

```sql
CASE 
    WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%'
    THEN 'V1'
    ...
END
```

---

## (3) 新工作流運作狀態驗證

### 📊 資料新鮮度檢查 (2025-12-25 ~ 2025-12-31)

| MView 名稱 | 行數 | 最後更新 | 狀態 |
|-----------|------|---------|------|
| mv_varinst_pivoted | 0 | 1970-01-01 | ❌ 無資料 |
| mv_emp_user_groups | 0 | 1970-01-01 | ❌ 無資料 |
| mv_emp_node_codes | 0 | 1970-01-01 | ❌ 無資料 |
| mv_emp_org_info | 0 | 1970-01-01 | ❌ 無資料 |
| mv_fact_task_vx_attribution | 0 | 1970-01-01 | ❌ 無資料 |
| mv_task_status_summary | 0 | 1970-01-01 | ❌ 無資料 |
| mv_l5_metrics_realtime | 0 | 1970-01-01 | ❌ 無資料 |
| mv_dim_config_user | 0 | 1970-01-01 | ❌ 無資料 |
| DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV | 0 | - | ❌ 無資料 |

### 🔴 **重大發現：所有 MView 都沒有資料！**

**來源表資料狀態：**

```
bronze.common_flowable_task_stats:
  - 總行數: 1,300,963
  - 日期範圍: 2025-07-24 ~ 2026-01-09
  - 日期數: 98

silver.mv_varinst_pivoted:
  - 總行數: 14,889
  - 日期範圍: 2026-01-21 ~ 2026-01-21 (只有今天的資料！)
  - 日期數: 1
```

**問題分析：**
- ✅ 來源表 (bronze.common_flowable_task_stats) 有 1.3M 行資料
- ✅ mv_varinst_pivoted 有 14,889 行資料（但只有 2026-01-21 的）
- ❌ mv_fact_task_vx_attribution 完全沒有資料
- ❌ 其他 MView 也都沒有資料

---

## (4) 舊工作流檢查

### ✅ 舊表掃描結果

**查詢：** 搜尋名稱包含 'old', 'legacy', 'v1' 的表

**結果：** 未發現明顯的舊表

**結論：** 沒有發現舊版工作流的表仍在運作

---

## (5) 問題根因分析

### 🔴 問題 1：MView 定義未完全更新

**症狀：** mv_fact_task_vx_attribution 仍使用舊 315% 規則

**根因：** 
- SQL 檔案 `sql/12_create_silver_mviews_layer2.sql` 中的定義已更新
- 但 ClickHouse 中的 MView 定義仍是舊版本
- 這表示 MView 沒有被重新建立

**證據：**
```
檔案定義 (sql/12_create_silver_mviews_layer2.sql):
  ✅ LIKE '315%'

ClickHouse 實際定義:
  ❌ IN ('3152600035', '3152600036', '3152600037')
```

### 🔴 問題 2：MView 沒有 POPULATE

**症狀：** MView 建立時沒有 POPULATE 標記

**根因：**
- MView 定義中缺少 `POPULATE` 關鍵字
- 導致 MView 在建立時沒有自動填充資料

**證據：**
```
SHOW CREATE TABLE silver.mv_fact_task_vx_attribution
  ❌ 沒有 POPULATE 關鍵字
```

### 🔴 問題 3：MView 沒有內部表

**症狀：** 查詢 `.inner.mv_fact_task_vx_attribution*` 沒有結果

**根因：**
- MView 沒有正確建立內部表
- 可能是因為沒有 POPULATE，或建立過程出錯

### 🔴 問題 4：mv_varinst_pivoted 只有今天的資料

**症狀：** mv_varinst_pivoted 只有 2026-01-21 的資料

**根因：**
- 該 MView 可能是今天才建立的
- 沒有回溯填充歷史資料（2025-12-25 ~ 2025-12-31）

---

## (6) 修正建議

### 🔧 修正步驟

#### 步驟 1：更新 MView 定義

**操作：** 重新建立 mv_fact_task_vx_attribution，使用新的 315% 規則

```sql
-- 1. 刪除舊 MView
DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution;

-- 2. 執行新的 SQL 定義
-- 使用 sql/12_create_silver_mviews_layer2.sql 中的定義
-- 確保包含 POPULATE 關鍵字
```

**預期結果：**
- ✅ MView 定義更新為新版本
- ✅ 使用新的 315% 規則 (LIKE '315%')
- ✅ 使用新的 NPE 判別邏輯 (varinst_name LIKE '%NPE%')

#### 步驟 2：確保 POPULATE 關鍵字

**檢查項目：**
```sql
-- 驗證 POPULATE 是否存在
SHOW CREATE TABLE silver.mv_fact_task_vx_attribution
-- 應該看到 "POPULATE" 關鍵字
```

**如果缺少 POPULATE：**
```sql
-- 需要重新建立 MView，添加 POPULATE
DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution;
-- 執行完整的 CREATE MATERIALIZED VIEW ... POPULATE AS ...
```

#### 步驟 3：手動填充歷史資料

**操作：** 如果 MView 沒有自動填充，需要手動填充

```sql
-- 方法 1：使用 INSERT INTO SELECT
INSERT INTO silver.mv_fact_task_vx_attribution
SELECT ... FROM bronze.common_flowable_task_stats
WHERE toDate(TaskCreateTime) BETWEEN '2025-12-25' AND '2025-12-31';

-- 方法 2：使用 REFRESH（如果支援）
REFRESH TABLE silver.mv_fact_task_vx_attribution;
```

#### 步驟 4：驗證其他 MView

**檢查清單：**
- [ ] mv_varinst_pivoted - 確保有 2025-12-25 ~ 2025-12-31 的資料
- [ ] mv_emp_user_groups - 確保有資料
- [ ] mv_emp_node_codes - 確保有資料
- [ ] mv_emp_org_info - 確保有資料
- [ ] mv_task_status_summary - 確保有資料
- [ ] mv_l5_metrics_realtime - 確保有資料
- [ ] mv_dim_config_user - 確保有資料

---

## (7) 驗證清單

### 修正前驗證

```sql
-- 1. 檢查 315% 規則
SHOW CREATE TABLE silver.mv_fact_task_vx_attribution
-- 查找: IN ('3152600035' 或 LIKE '315%'

-- 2. 檢查 POPULATE
SHOW CREATE TABLE silver.mv_fact_task_vx_attribution
-- 查找: POPULATE 關鍵字

-- 3. 檢查資料
SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution
WHERE toDate(task_create_time) BETWEEN '2025-12-25' AND '2025-12-31'
-- 預期: > 0
```

### 修正後驗證

```sql
-- 1. 驗證 315% 規則已更新
SHOW CREATE TABLE silver.mv_fact_task_vx_attribution
-- 應該看到: LIKE '315%'

-- 2. 驗證 POPULATE 存在
SHOW CREATE TABLE silver.mv_fact_task_vx_attribution
-- 應該看到: POPULATE

-- 3. 驗證資料已填充
SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution
WHERE toDate(task_create_time) BETWEEN '2025-12-25' AND '2025-12-31'
-- 預期: > 0

-- 4. 驗證 NPE 邏輯
SELECT COUNT(DISTINCT vx_subtype) FROM silver.mv_fact_task_vx_attribution
WHERE vx_subtype IN ('V1_NPE', 'V1_MFG')
-- 預期: 2
```

---

## 結論

### 🚨 當前狀態

| 項目 | 狀態 | 說明 |
|------|------|------|
| **新版工作流定義** | ⚠️ 部分更新 | mv_fact_task_vx_attribution 仍使用舊 315% 規則 |
| **新版工作流運作** | ❌ 未運作 | 所有 MView 都沒有資料 |
| **舊工作流** | ✅ 已清理 | 未發現舊表仍在運作 |

### 📋 立即行動

1. **優先級 1（緊急）：** 重新建立 mv_fact_task_vx_attribution，使用新的 315% 規則
2. **優先級 2（高）：** 確保所有 MView 都有 POPULATE 關鍵字
3. **優先級 3（高）：** 手動填充 2025-12-25 ~ 2025-12-31 的歷史資料
4. **優先級 4（中）：** 驗證其他 MView 的資料完整性

### ✅ 預期結果

修正完成後：
- ✅ mv_fact_task_vx_attribution 使用新的 315% 規則 (LIKE '315%')
- ✅ 所有 MView 都有資料
- ✅ 新工作流正常運作
- ✅ 資料時間範圍涵蓋 2025-12-25 ~ 2025-12-31

---

**報告簽署：** Kiro Agent  
**驗證日期：** 2026-01-22  
**下一步：** 等待用戶確認是否執行修正步驟
