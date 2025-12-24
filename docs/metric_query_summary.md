# 指標查詢統整

## ✅ 已完成指標 (12個)

### 1. 業務事件總歷時
```sql
SELECT BIZ_EVENT_KEY, TOTAL_DURATION_SEC
FROM silver.V_HI_BIZ_EVENT_INFO
WHERE FINAL_END_TIME IS NOT NULL
```

### 2. 流程執行總時間
```sql
SELECT BIZ_EVENT_KEY, TOTAL_PROC_DURATION_SEC
FROM silver.V_HI_BIZ_EVENT_INFO
```

### 3. 任務處理總時間
```sql
SELECT BIZ_EVENT_KEY, TOTAL_WORK_DURATION_SEC
FROM silver.V_HI_BIZ_EVENT_INFO
```

### 4. 流程總歷時
```sql
SELECT PROC_INST_ID, DURATION_SEC
FROM silver.V_HI_PROCINST_NODE
WHERE END_TIME IS NOT NULL
```

### 5. 任務閒置時長
```sql
SELECT TASK_ID, IDLE_DURATION_SEC
FROM silver.V_HI_PROC_TASK_NODE
WHERE CLAIM_TIME IS NOT NULL
```

### 6. 個人處理時長
```sql
SELECT TASK_ID, WORK_DURATION_SEC
FROM silver.V_HI_PROC_TASK_NODE
WHERE CLAIM_TIME IS NOT NULL AND END_TIME IS NOT NULL
```

### 7. 任務總歷時
```sql
SELECT TASK_ID, TOTAL_DURATION_SEC
FROM silver.V_HI_PROC_TASK_NODE
WHERE END_TIME IS NOT NULL
```

### 8. 在途業務事件總數
```sql
SELECT count(*) AS CNT
FROM silver.V_HI_BIZ_EVENT_INFO
WHERE FINAL_END_TIME IS NULL
```

### 9. 在途任務總數
```sql
SELECT sum(TASK_TODO_CNT + TASK_DOING_CNT) AS CNT
FROM silver.V_HI_BIZ_EVENT_INFO
WHERE FINAL_END_TIME IS NULL
```

### 10. 平均業務事件總歷時
```sql
SELECT avg(TOTAL_DURATION_SEC) AS AVG_DURATION_SEC
FROM silver.V_HI_BIZ_EVENT_INFO
WHERE FINAL_END_TIME IS NOT NULL
```

### 11. 平均任務處理時長
```sql
SELECT avg(WORK_DURATION_SEC) AS AVG_WORK_SEC
FROM silver.V_HI_PROC_TASK_NODE AS t
JOIN silver.V_HI_BIZ_EVENT_INFO AS b ON t.BUSINESS_KEY = b.BIZ_EVENT_KEY
WHERE b.FINAL_END_TIME IS NOT NULL
  AND t.TASK_STATUS = 'DONE'
```

### 12. 在途任務數 - 依部門
```sql
SELECT 
    coalesce(e.DEPT_NAME, 'Unknown') AS DEPT_NAME,
    count(*) AS TASK_CNT
FROM silver.V_HI_PROC_TASK_NODE AS t
LEFT JOIN bronze.common_hr_employee AS e ON t.ASSIGNEE = e.EMP_NO
WHERE t.TASK_STATUS IN ('TODO', 'DOING')
GROUP BY coalesce(e.DEPT_NAME, 'Unknown')
ORDER BY TASK_CNT DESC
```

### 13. 在途任務數 - 依廠區
```sql
SELECT 
    coalesce(v.TEXT_, 'Unknown') AS PLANT,
    count(*) AS TASK_CNT
FROM silver.V_HI_PROC_TASK_NODE AS t
LEFT JOIN bronze.bpm_act_hi_varinst AS v 
    ON t.PROC_INST_ID = v.PROC_INST_ID_ AND v.NAME_ = 'plant'
WHERE t.TASK_STATUS IN ('TODO', 'DOING')
GROUP BY coalesce(v.TEXT_, 'Unknown')
ORDER BY TASK_CNT DESC
```

### 14. 在途任務數 - 依地區
```sql
SELECT 
    coalesce(v.TEXT_, 'Unknown') AS REGION,
    count(*) AS TASK_CNT
FROM silver.V_HI_PROC_TASK_NODE AS t
LEFT JOIN bronze.bpm_act_hi_varinst AS v 
    ON t.PROC_INST_ID = v.PROC_INST_ID_ AND v.NAME_ = 'region'
WHERE t.TASK_STATUS IN ('TODO', 'DOING')
GROUP BY coalesce(v.TEXT_, 'Unknown')
ORDER BY TASK_CNT DESC
```

### 15. 在途任務數 - 依人員
```sql
SELECT 
    CASE 
        WHEN t.ASSIGNEE IS NOT NULL AND t.ASSIGNEE != '' 
        THEN t.ASSIGNEE 
        ELSE 'Unassigned' 
    END AS ASSIGNEE_NAME,
    count(*) AS TASK_CNT
FROM silver.V_HI_PROC_TASK_NODE AS t
WHERE t.TASK_STATUS IN ('TODO', 'DOING')
GROUP BY ASSIGNEE_NAME
ORDER BY TASK_CNT DESC
```

### 16. 在途流程健康度快照
```sql
SELECT 
    coalesce(pd.NAME_, 'Unknown') AS PROC_DEF_NAME,
    count(DISTINCT b.BIZ_EVENT_KEY) AS EVENT_CNT
FROM silver.V_HI_BIZ_EVENT_INFO AS b
LEFT JOIN bronze.bpm_act_hi_procinst AS p ON b.BIZ_EVENT_KEY = p.BUSINESS_KEY_
LEFT JOIN bronze.bpm_act_re_procdef AS pd ON p.PROC_DEF_ID_ = pd.ID_
WHERE b.FINAL_END_TIME IS NULL
GROUP BY coalesce(pd.NAME_, 'Unknown')
ORDER BY EVENT_CNT DESC
```

### 17. 事件自動完成率 ✅ (已完成)
**判斷邏輯**：DONE_AUTO = 有 ASSIGNEE、沒有 CLAIM_TIME、有 END_TIME（任務被指派但沒被認領就直接完成）

```sql
-- 整體自動完成率
SELECT 
    round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) AS auto_rate
FROM silver.V_HI_PROC_TASK_NODE

-- 依流程定義分組
SELECT 
    PROC_DEF_NAME,
    countIf(TASK_STATUS = 'DONE') AS done_cnt,
    countIf(TASK_STATUS = 'DONE_AUTO') AS auto_cnt,
    round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) AS auto_rate
FROM silver.V_HI_PROC_TASK_NODE
WHERE TASK_STATUS IN ('DONE', 'DONE_AUTO')
GROUP BY PROC_DEF_NAME
```

---

## ⚠️ 未完成指標 (1個)

### 1. 逾期在途業務事件數
**缺少**：`HealthSettings` 表（定義紅燈天數門檻）

**備註**：參考環境 (flowable_analytics) 也沒有此表，逾期判斷可能在應用層處理

**查詢框架**（待補 HealthSettings）：
```sql
SELECT count(DISTINCT b.BIZ_EVENT_KEY) AS OVERDUE_CNT
FROM silver.V_HI_BIZ_EVENT_INFO AS b
LEFT JOIN bronze.bpm_act_hi_procinst AS p ON b.BIZ_EVENT_KEY = p.BUSINESS_KEY_
LEFT JOIN bronze.bpm_act_hi_varinst AS v ON p.PROC_INST_ID_ = v.PROC_INST_ID_ AND v.NAME_ = 'factory'
-- LEFT JOIN HealthSettings AS hs ON v.TEXT_ = hs.FactoryName
WHERE b.FINAL_END_TIME IS NULL
  -- AND dateDiff('day', b.FIRST_START_TIME, now()) > hs.RedThresholdDays
```

---

## 📊 View 與變數來源對照

| 欄位 | 來源表 | 關聯方式 |
|------|--------|---------|
| `plant` | `bpm_act_hi_varinst` | `NAME_ = 'plant'`, JOIN by `PROC_INST_ID_` |
| `factory` | `bpm_act_hi_varinst` | `NAME_ = 'factory'`, JOIN by `PROC_INST_ID_` |
| `region` | `bpm_act_hi_varinst` | `NAME_ = 'region'`, JOIN by `PROC_INST_ID_` |
| 流程定義名稱 | `bpm_act_re_procdef` | JOIN by `PROC_DEF_ID_` |
| 員工部門 | `common_hr_employee` | JOIN by `EmpCode = ASSIGNEE` |

---

## 📋 階段完成狀態

### Phase 1-4: ✅ 已完成
| Phase | 內容 | 狀態 |
|-------|------|------|
| Phase 1 | 新增 `V_PROC_VARIABLES_PIVOTED` | ✅ |
| Phase 2 | 擴充 `V_HI_PROC_TASK_NODE` (加入 PLANT/FACTORY/REGION/PROC_DEF_NAME/DEPT_NAME) | ✅ |
| Phase 3 | 擴充 `V_HI_PROCINST_NODE` (加入 DEPTH/SUPER_ID/PROC_STATE) | ✅ |
| Phase 4 | 擴充 `V_HI_BIZ_EVENT_INFO` (加入 FIRST_PROC_DEF_NAME) | ✅ |
| Phase 5a | 更新 TASK_STATUS 判斷邏輯 (DONE_AUTO) | ✅ |
| Phase 5b | HealthSettings 表 (逾期判斷) | ⏸️ 暫緩 |

### 使用的 Bronze 表 (5 張)

| 表 | 用途 | 關鍵欄位 |
|-----|------|---------|
| `bpm_act_hi_procinst` | 流程實例歷史 | PROC_INST_ID_, BUSINESS_KEY_, START_TIME_, END_TIME_, SUPER_PROCESS_INSTANCE_ID_ |
| `bpm_act_hi_taskinst` | 任務實例歷史 | ID_, PROC_INST_ID_, ASSIGNEE_, CLAIM_TIME_, END_TIME_, DELETE_REASON_ |
| `bpm_act_hi_varinst` | 流程變數 | PROC_INST_ID_, NAME_, TEXT_ (plant/factory/region) |
| `bpm_act_re_procdef` | 流程定義 | ID_, NAME_ |
| `common_hr_employee` | 員工資料 | EmpCode, DeptCodeLname |

### 已建立的 Silver Views (4 張)

| View | Grain | 用途 |
|------|-------|------|
| `silver.V_PROC_VARIABLES_PIVOTED` | PROC_INST_ID | 流程變數樞紐化 (plant/factory/region) |
| `silver.V_HI_PROC_TASK_NODE` | Task ID | 任務節點層，含狀態/時長/部門/廠區 |
| `silver.V_HI_PROCINST_NODE` | PROC_INST_ID | 流程實例層，含階層/狀態 |
| `silver.V_HI_BIZ_EVENT_INFO` | BUSINESS_KEY | 業務事件層，聚合統計 |
