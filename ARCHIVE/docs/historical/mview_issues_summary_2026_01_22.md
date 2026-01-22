# ClickHouse MView 工作流驗證 - 問題摘要

**驗證日期：** 2026-01-22  
**驗證狀態：** 🚨 發現重大問題

---

## 快速診斷結果

### 📊 MView 統計

- **總數：** 12 個 MView
- **新版工作流：** 2 個 ✅
- **舊版工作流：** 0 個 ✅
- **混合版本：** 1 個 ⚠️
- **有資料：** 3 個 (都是 View，不是 MView)
- **無資料：** 9 個 ❌

---

## 🚨 關鍵問題

### 問題 1：MView 定義未完全更新

**MView：** `silver.mv_fact_task_vx_attribution`

**問題：** 仍使用舊 315% 規則

```
❌ 實際 DDL:
   IN ('3152600035', '3152600036', '3152600037')

✅ 應該是:
   LIKE '315%'
```

**影響：** 無法正確識別所有 315 開頭的工單號

**修正：** 需要 DROP 並重新建立 MView

---

### 問題 2：所有 MView 都沒有資料

**症狀：**
```
mv_fact_task_vx_attribution:     0 行 ❌
mv_varinst_pivoted:              0 行 ❌
mv_emp_user_groups:              0 行 ❌
mv_emp_node_codes:               0 行 ❌
mv_emp_org_info:                 0 行 ❌
mv_task_status_summary:          0 行 ❌
mv_l5_metrics_realtime:          0 行 ❌
mv_dim_config_user:              0 行 ❌
DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV: 0 行 ❌
```

**根因：**
1. MView 定義中缺少 `POPULATE` 關鍵字
2. MView 沒有自動填充資料
3. 沒有手動填充歷史資料

**影響：** 新工作流完全未運作

**修正：** 
1. 重新建立 MView，添加 POPULATE
2. 手動填充 2025-12-25 ~ 2025-12-31 的資料

---

### 問題 3：mv_varinst_pivoted 只有今天的資料

**症狀：**
```
mv_varinst_pivoted:
  - 總行數: 14,889
  - 日期範圍: 2026-01-21 ~ 2026-01-21 (只有今天！)
```

**根因：** MView 可能是今天才建立的，沒有回溯填充

**影響：** 無法分析 2025-12-25 ~ 2025-12-31 的資料

**修正：** 手動填充歷史資料

---

## ✅ 正常運作的部分

### 來源表資料完整

```
bronze.common_flowable_task_stats:
  - 總行數: 1,300,963 ✅
  - 日期範圍: 2025-07-24 ~ 2026-01-09 ✅
```

### View 正常運作

```
vw_fact_task_vx_attribution_realtime:  1,300,963 行 ✅
vw_fact_task_with_five_level:          1,300,963 行 ✅
vw_l5_metrics_five_level:              8,475 行 ✅
```

---

## 🔧 修正步驟

### 步驟 1：重新建立 mv_fact_task_vx_attribution

```sql
-- 1. 刪除舊 MView
DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution;

-- 2. 執行新定義（使用 sql/12_create_silver_mviews_layer2.sql）
-- 確保包含 POPULATE 關鍵字和新的 315% 規則
```

### 步驟 2：驗證 POPULATE

```sql
SHOW CREATE TABLE silver.mv_fact_task_vx_attribution
-- 應該看到 "POPULATE" 關鍵字
```

### 步驟 3：驗證 315% 規則

```sql
SHOW CREATE TABLE silver.mv_fact_task_vx_attribution
-- 應該看到 "LIKE '315%'" 而不是 "IN ('3152600035'"
```

### 步驟 4：驗證資料

```sql
SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution
WHERE toDate(task_create_time) BETWEEN '2025-12-25' AND '2025-12-31'
-- 預期: > 0
```

---

## 📋 檢查清單

- [ ] 重新建立 mv_fact_task_vx_attribution
- [ ] 驗證 POPULATE 關鍵字存在
- [ ] 驗證 315% 規則已更新為 LIKE '315%'
- [ ] 驗證資料已填充
- [ ] 檢查其他 MView 的資料完整性
- [ ] 驗證 NPE 邏輯正確

---

## 結論

**新版工作流狀態：** ❌ 未完全部署

**主要問題：**
1. ❌ MView 定義未完全更新（315% 規則仍是舊版）
2. ❌ MView 沒有資料（缺少 POPULATE 或未手動填充）
3. ⚠️ 歷史資料未回溯填充

**建議：** 立即執行修正步驟，確保新工作流正常運作

---

**詳細報告：** 見 `docs/mview_workflow_verification_report_2026_01_22.md`
