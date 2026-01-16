# View vs RMV SQL 語意等價性分析

## 分析前提
- 假設 bronze 層資料在同一時間點完全一致
- 不討論資料延遲或補寫問題
- 僅針對 SQL 本身的正確性與等價性進行檢視

---

## 1. V_PROC_VARIABLES_PIVOTED vs RMV_PROC_VARIABLES_PIVOTED

### 1.1 FROM / WHERE 條件比較

| 項目 | View | RMV | 等價性 |
|------|------|-----|--------|
| FROM | `bronze.bpm_act_hi_varinst` | `bronze.bpm_act_hi_varinst` | ✅ |
| WHERE NAME_ IN | 11 個變數 | 6 個變數 | ❌ 不等價 |
| WHERE PROC_INST_ID_ IS NOT NULL | ✅ | ✅ | ✅ |
| WHERE TASK_ID_ IS NULL | ✅ | ❌ 缺少 | ❌ 不等價 |

**View WHERE 條件:**
```sql
WHERE NAME_ IN ('plant', 'factory', 'region', 'sapPlant', 'sapProductGroup', 
                'lineName', 'modelName', 'moNumber', 'scheduleNumber', 
                'initiator', '_PROCESS_NODE_INFO')
  AND PROC_INST_ID_ IS NOT NULL
  AND TASK_ID_ IS NULL
```

**RMV WHERE 條件:**
```sql
WHERE NAME_ IN ('plant', 'factory', 'region', 'sapPlant', 'lineName', 'modelName')
  AND PROC_INST_ID_ IS NOT NULL
-- 缺少 TASK_ID_ IS NULL
```

### 1.2 GROUP BY 粒度比較

| 項目 | View | RMV | 等價性 |
|------|------|-----|--------|
| GROUP BY | `PROC_INST_ID_` | `PROC_INST_ID_` | ✅ |

### 1.3 聚合函數比較

| 欄位 | View | RMV | 等價性 |
|------|------|-----|--------|
| PLANT | `anyIf(TEXT_, NAME_ = 'plant')` | `anyIf(TEXT_, NAME_ = 'plant')` | ✅ |
| FACTORY | `anyIf(TEXT_, NAME_ = 'factory')` | `anyIf(TEXT_, NAME_ = 'factory')` | ✅ |
| REGION | `anyIf(TEXT_, NAME_ = 'region')` | `anyIf(TEXT_, NAME_ = 'region')` | ✅ |
| SAP_PLANT | `anyIf(TEXT_, NAME_ = 'sapPlant')` | `anyIf(TEXT_, NAME_ = 'sapPlant')` | ✅ |
| SAP_PROD_GRP | `anyIf(TEXT_, NAME_ = 'sapProductGroup')` | ❌ 缺少 | ❌ |
| LINE_NAME | `anyIf(TEXT_, NAME_ = 'lineName')` | `anyIf(TEXT_, NAME_ = 'lineName')` | ✅ |
| MODEL_NAME | `anyIf(TEXT_, NAME_ = 'modelName')` | `anyIf(TEXT_, NAME_ = 'modelName')` | ✅ |
| MO_NUMBER | `anyIf(TEXT_, NAME_ = 'moNumber')` | ❌ 缺少 | ❌ |
| SCH_NUMBER | `anyIf(TEXT_, NAME_ = 'scheduleNumber')` | ❌ 缺少 | ❌ |
| INITIATOR | `anyIf(TEXT_, NAME_ = 'initiator')` | ❌ 缺少 | ❌ |
| PROC_NODE_INFO | `anyIf(TEXT_, NAME_ = '_PROCESS_NODE_INFO')` | ❌ 缺少 | ❌ |
| FIRST_VAR_CREATED_AT | `min(CREATE_TIME_)` | ❌ 缺少 | ❌ |
| LAST_VAR_UPDATED_AT | `max(LAST_UPDATED_TIME_)` | ❌ 缺少 | ❌ |

### 1.4 結論

| 面向 | 結論 |
|------|------|
| FROM | ✅ 等價 |
| WHERE | ❌ **不等價** - RMV 缺少 `TASK_ID_ IS NULL` 條件，可能包含任務層變數 |
| GROUP BY | ✅ 等價 |
| 聚合函數 | ❌ **不等價** - RMV 缺少 7 個欄位 |
| **整體** | ❌ **不等價** |

---

## 2. V_TASK_VARIABLES_PIVOTED vs RMV

### 結論
| 面向 | 結論 |
|------|------|
| **整體** | ❌ **RMV 不存在** - View 有 `V_TASK_VARIABLES_PIVOTED`，但 RMV 沒有對應表 |

---

## 3. V_HI_PROC_TASK_NODE vs RMV_HI_PROC_TASK_NODE

### 3.1 FROM / JOIN 比較

| JOIN | View | RMV | 等價性 |
|------|------|-----|--------|
| 主表 | `bronze.bpm_act_hi_taskinst` | `bronze.bpm_act_hi_taskinst` | ✅ |
| procinst | `LEFT JOIN bronze.bpm_act_hi_procinst` | `LEFT JOIN bronze.bpm_act_hi_procinst` | ✅ |
| proc_variables | `LEFT JOIN silver.V_PROC_VARIABLES_PIVOTED` | `LEFT JOIN silver.RMV_PROC_VARIABLES_PIVOTED` | ⚠️ 來源不同 |
| task_variables | `LEFT JOIN silver.V_TASK_VARIABLES_PIVOTED` | ❌ 缺少 | ❌ |
| identitylink | `LEFT JOIN (子查詢 bpm_act_hi_identitylink)` | ❌ 缺少 | ❌ |
| procdef | `LEFT JOIN bronze.bpm_act_re_procdef` | `LEFT JOIN bronze.bpm_act_re_procdef` | ✅ |
| employee | `LEFT JOIN bronze.common_hr_employee` | `LEFT JOIN bronze.common_hr_employee` | ✅ |

### 3.2 欄位比較

| 欄位 | View | RMV | 等價性 |
|------|------|-----|--------|
| 基礎欄位 (TASK_ID, PROC_INST_ID, etc.) | ✅ | ✅ | ✅ |
| TASK_STATUS | ✅ (multiIf) | ✅ (multiIf) | ✅ 邏輯相同 |
| TASK_BYPASS | ✅ | ❌ 缺少 | ❌ |
| TASK_CANDIDATE_USER | ✅ | ❌ 缺少 | ❌ |
| TASK_AUTO_COMPLETE | ✅ | ❌ 缺少 | ❌ |
| CANDIDATE_USERS_LINK | ✅ | ❌ 缺少 | ❌ |
| SAP_PROD_GRP | ✅ | ❌ 缺少 | ❌ |
| MO_NUMBER | ✅ | ❌ 缺少 | ❌ |
| SCH_NUMBER | ✅ | ❌ 缺少 | ❌ |
| PROC_DEF_KEY | ✅ | ❌ 缺少 | ❌ |

### 3.3 結論

| 面向 | 結論 |
|------|------|
| FROM | ✅ 等價 |
| JOIN | ❌ **不等價** - RMV 缺少 task_variables 和 identitylink JOIN |
| 欄位 | ❌ **不等價** - RMV 缺少 9 個欄位 |
| TASK_STATUS 邏輯 | ✅ 等價 |
| **整體** | ❌ **不等價** |

---

## 4. V_HI_PROCINST_NODE vs RMV_HI_PROCINST_NODE

### 4.1 FROM / JOIN 比較

| JOIN | View | RMV | 等價性 |
|------|------|-----|--------|
| 主表 | `bronze.bpm_act_hi_procinst` | `bronze.bpm_act_hi_procinst` | ✅ |
| proc_variables | `LEFT JOIN silver.V_PROC_VARIABLES_PIVOTED` | `LEFT JOIN silver.RMV_PROC_VARIABLES_PIVOTED` | ⚠️ 來源不同 |
| procdef | `LEFT JOIN bronze.bpm_act_re_procdef` | `LEFT JOIN bronze.bpm_act_re_procdef` | ✅ |

### 4.2 欄位比較

| 欄位 | View | RMV | 等價性 |
|------|------|-----|--------|
| 基礎欄位 | ✅ | ✅ | ✅ |
| PROC_STATE | ✅ (multiIf) | ✅ (multiIf) | ✅ 邏輯相同 |
| SAP_PROD_GRP | ✅ | ❌ 缺少 | ❌ |
| MO_NUMBER | ✅ | ❌ 缺少 | ❌ |
| SCH_NUMBER | ✅ | ❌ 缺少 | ❌ |
| INITIATOR | ✅ | ❌ 缺少 | ❌ |
| PROC_NODE_INFO | ✅ | ❌ 缺少 | ❌ |
| PROC_DEF_KEY | ✅ | ❌ 缺少 | ❌ |
| PROC_DEF_VERSION | ✅ | ❌ 缺少 | ❌ |

### 4.3 結論

| 面向 | 結論 |
|------|------|
| FROM | ✅ 等價 |
| JOIN | ⚠️ 語意相同但來源不同 |
| 欄位 | ❌ **不等價** - RMV 缺少 7 個欄位 |
| PROC_STATE 邏輯 | ✅ 等價 |
| **整體** | ❌ **不等價** (欄位數量不同) |

---

## 5. V_HI_BIZ_EVENT_INFO vs RMV_HI_BIZ_EVENT_INFO

### 5.1 FROM / WHERE / GROUP BY 比較

| 項目 | View | RMV | 等價性 |
|------|------|-----|--------|
| 子查詢 p FROM | `bronze.bpm_act_hi_procinst` | `bronze.bpm_act_hi_procinst` | ✅ |
| 子查詢 p WHERE | `BUSINESS_KEY_ IS NOT NULL AND BUSINESS_KEY_ != ''` | 相同 | ✅ |
| 子查詢 p GROUP BY | `BUSINESS_KEY_` | `BUSINESS_KEY_` | ✅ |
| 子查詢 t FROM | `bronze.bpm_act_hi_taskinst INNER JOIN bronze.bpm_act_hi_procinst` | 相同 | ✅ |
| 子查詢 t WHERE | `BUSINESS_KEY_ IS NOT NULL AND BUSINESS_KEY_ != ''` | 相同 | ✅ |
| 子查詢 t GROUP BY | `BUSINESS_KEY_` | `BUSINESS_KEY_` | ✅ |
| 主查詢 JOIN | `p LEFT JOIN t ON BUSINESS_KEY` | 相同 | ✅ |

### 5.2 聚合函數比較

| 欄位 | View | RMV | 等價性 |
|------|------|-----|--------|
| FIRST_START_TIME | `min(pi.START_TIME_)` | `min(pi.START_TIME_)` | ✅ |
| FINAL_END_TIME | `if(countIf(...) = 0, max(...), NULL)` | 相同 | ✅ |
| TOTAL_DURATION_SEC | `if(countIf(...) = 0, dateDiff(...), NULL)` | 相同 | ✅ |
| TOTAL_PROC_DURATION_SEC | `sum(if(...))` | `sum(if(...))` | ✅ |
| PROCESS_COUNT | `count(*)` | `count(*)` | ✅ |
| IS_IN_PROGRESS | `if(countIf(...) > 0, 1, 0)` | 相同 | ✅ |
| FIRST_PROC_DEF_NAME | `anyIf(pd.NAME_, ...)` | `anyIf(pd.NAME_, ...)` | ✅ |
| TASK_TODO_CNT | `countIf(...)` | `countIf(...)` | ✅ |
| TASK_DOING_CNT | `countIf(...)` | `countIf(...)` | ✅ |
| TASK_DONE_CNT | `countIf(...)` | `countIf(...)` | ✅ |
| TASK_AUTOCOMPLETE_CNT | `countIf(...)` | `countIf(...)` | ✅ |
| TASK_CANCELLED_CNT | `countIf(...)` | `countIf(...)` | ✅ |
| TOTAL_WORK_DURATION_SEC | `sum(if(...))` | `sum(if(...))` | ✅ |

### 5.3 結論

| 面向 | 結論 |
|------|------|
| FROM | ✅ 等價 |
| WHERE | ✅ 等價 |
| GROUP BY | ✅ 等價 |
| 聚合函數 | ✅ 等價 |
| JOIN | ✅ 等價 |
| **整體** | ✅ **語意等價** |

---

## 總結

### 語意安全等價的部分

| View | RMV | 等價性 |
|------|-----|--------|
| V_HI_BIZ_EVENT_INFO | RMV_HI_BIZ_EVENT_INFO | ✅ **完全等價** |

### 語意不等價的部分

| View | RMV | 差異原因 |
|------|-----|----------|
| V_PROC_VARIABLES_PIVOTED | RMV_PROC_VARIABLES_PIVOTED | RMV 缺少 5 個變數欄位、缺少 `TASK_ID_ IS NULL` 條件 |
| V_TASK_VARIABLES_PIVOTED | - | RMV 不存在 |
| V_HI_PROC_TASK_NODE | RMV_HI_PROC_TASK_NODE | RMV 缺少 task_variables JOIN、identitylink JOIN、9 個欄位 |
| V_HI_PROCINST_NODE | RMV_HI_PROCINST_NODE | RMV 缺少 7 個欄位 |

### RMV 特有限制

1. **ReplacingMergeTree 引擎**：RMV 使用 `ReplacingMergeTree()` 引擎，在 `FINAL` 查詢前可能存在重複資料
2. **ORDER BY 限制**：RMV 必須指定 `ORDER BY`，這決定了去重的 key
3. **Nullable 欄位**：RMV 的 `ORDER BY` 欄位不能是 Nullable（需要 `allow_nullable_key = 1`）

### 建議

1. **同步 RMV 定義**：將 RMV 的 SQL 更新為與 View 完全一致
2. **新增 RMV_TASK_VARIABLES_PIVOTED**：補齊缺少的任務變數 RMV
3. **更新 RMV_PROC_VARIABLES_PIVOTED**：加入缺少的變數欄位和 `TASK_ID_ IS NULL` 條件
4. **更新 RMV_HI_PROC_TASK_NODE**：加入 task_variables 和 identitylink JOIN
5. **更新 RMV_HI_PROCINST_NODE**：加入缺少的欄位
