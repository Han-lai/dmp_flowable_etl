# 實作手冊 3：Silver 與 Gold 層：業務指標 (KPI) 運算邏輯與 SQL 規格 (L5 核心算法)

本手冊詳述數據從原始事實 (Bronze) 轉化為業務指標 (Gold) 的核心算法，是整套系統的「業務靈魂」。

---

## 1. Silver Layer: 數據清洗與五階對齊
在 `silver.mv_fact_task_vx` 中，我們實作了複雜的業務判定邏輯。

### **1.1 五階維度 (Vx) 判定代碼**
系統優先考慮「廠區特權規則」，其次才是原始任務定義鍵。
```sql
CASE 
    -- 規則 1：DG3 / NPE 廠區特權 (工單號碼 196, 199... 強制轉 V1)
    WHEN (plant = 'DG3' OR factory LIKE '%NPE%')
         AND substring(mo_number, 1, 3) IN ('196','199','200','210','212',...) 
    THEN 'V1'
    
    -- 規則 2：自動從 TASK_DEF_KEY_ 提取
    WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
    WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
    WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
    ELSE 'Unknown'
END AS vx_type
```

### **1.2 數據過濾規格 (Exclusion Logic)**
```sql
CASE 
    WHEN tb.LONG_ = 1 THEN 1               -- 使用者手動 bypass
    WHEN mo_number LIKE 'Q%' OR mo_number LIKE 'R%' THEN 1 -- 測試/研發工單
    WHEN t.NAME_ LIKE '%Notify%' THEN 1    -- 系統自動通知節點
    ELSE 0
END AS is_excluded
```

---

## 2. Gold Layer: 指標聚合與物理化
在 `gold.rmv_l5_task_completion_phys` 中，我們透過「週窗物理化」實現穩定計算。

### **2.1 快照爆炸機制 (`ARRAY JOIN`)**
```sql
SELECT
    snapshot_date,
    countIf(snapshot_date < toDate(task_claim_date)) AS todo_count,
    countIf(snapshot_date >= toDate(task_claim_date) AND snapshot_date < toDate(task_end_date)) AS doing_count
FROM silver.mv_fact_task_vx
-- 核心：將一列擴展為三列 (Start/Claim/End 三個時間點)
ARRAY JOIN arrayDistinct(arrayFilter(d -> d IS NOT NULL, 
    [task_start_date, task_claim_date, task_end_date])) AS snapshot_date
```

### **2.2 累積在途 (Acc) 計算公式**
使用 `CROSS JOIN` 與日期區間判斷來實現滾動去重：
```sql
SELECT
    dates.snapshot_date,
    uniqExact(tasks.task_id) AS acc_todo_doing
FROM dates_stream CROSS JOIN tasks_stream
WHERE tasks.task_start_date <= dates.snapshot_date
  AND (tasks.task_end_date IS NULL OR tasks.task_end_date > dates.snapshot_date)
```

---
> [!NOTE]
> **維護與更新流程**：本系統已完全轉向物理化 (Physicalization)。若修改了 V1/V2 判定邏輯，需執行以下指令進行全量補分 (Backfill)：
> ```powershell
> python scripts/etl/execute_etl.py --backfill --low-ram
> ```

---
**文件維護資訊**
*   **版本號**：v1.0.0
*   **更新日期**：2026-03-12
*   **維護人員**：albee
