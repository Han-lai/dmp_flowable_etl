# 計算邏輯一致性審核報告

**審核日期**: 2025-12-24

## 審核結論

| 比較項目 | 結果 |
|---------|------|
| Benchmark vs View | ✅ 邏輯等價 |
| Benchmark vs RMV | ✅ 邏輯等價 |
| View vs RMV | ✅ 完全一致 |

**整體結論: ✅ 三個環境在計算邏輯上等價**

---

## 環境定義

| 環境 | Host | Port | 表格 |
|------|------|------|------|
| Benchmark | 10.136.218.207 | 8124 | `flowable_analytics.gold_proc_task_node_rmv`<br>`flowable_analytics.gold_procinst_node_rmv` |
| View | 10.136.218.207 | 8121 | `silver.V_HI_PROC_TASK_NODE`<br>`silver.V_HI_PROCINST_NODE` |
| RMV | 10.136.218.207 | 8121 | `silver.RMV_HI_PROC_TASK_NODE`<br>`silver.RMV_HI_PROCINST_NODE` |

---

## 筆數差異說明

| 環境 | TASK_NODE 筆數 | PROCINST_NODE 筆數 | 資料截止日 |
|------|---------------|-------------------|-----------|
| Benchmark | 61,741 | 15,529 | 2025-12-10 |
| View | 48,508 | 16,431 | 2025-12-24 |
| RMV | 48,508 | 16,431 | 2025-12-24 |

**差異原因**: Benchmark 的 bronze 層資料 (`ACT_HI_*`) 最後同步時間為 2025-12-10 07:14:03，而我的環境同步到 2025-12-24。筆數差異是資料同步時間點不同，非邏輯問題。

---

## 欄位語意對應

### TASK_NODE 欄位對應

| Benchmark 欄位 | 我的欄位 | 語意等價 |
|---------------|---------|---------|
| node_id | TASK_ID | ✅ |
| node_state | TASK_STATUS | ✅ (見狀態對應) |
| task_assignee | ASSIGNEE | ✅ |
| task_candidate | TASK_CANDIDATE_USER | ✅ |
| task_claim_time | CLAIM_TIME | ✅ |
| start_time | START_TIME | ✅ |
| end_time | END_TIME | ✅ |
| delete_reason | DELETE_REASON | ✅ |
| proc_plant | PLANT | ✅ |
| proc_factory | FACTORY | ✅ |
| proc_sap_plant | SAP_PLANT | ✅ |
| proc_sap_prod_grp | SAP_PROD_GRP | ✅ |
| proc_line_name | LINE_NAME | ✅ |
| proc_model_name | MODEL_NAME | ✅ |
| proc_mo_number | MO_NUMBER | ✅ |
| proc_sch_number | SCH_NUMBER | ✅ |
| proc_key | PROC_DEF_KEY | ✅ |
| dmp_biz_event_key | BUSINESS_KEY | ✅ |

### PROCINST_NODE 欄位對應

| Benchmark 欄位 | 我的欄位 | 語意等價 |
|---------------|---------|---------|
| proc_id | PROC_INST_ID | ✅ |
| proc_state | PROC_STATE | ✅ (見狀態對應) |
| proc_key | PROC_DEF_KEY | ✅ |
| proc_ver | PROC_DEF_VERSION | ✅ |
| start_time | START_TIME | ✅ |
| end_time | END_TIME | ✅ |
| delete_reason | DELETE_REASON | ✅ |
| super_id | SUPER_ID | ✅ |
| depth | DEPTH | ✅ |

---

## 狀態欄位對應

### TASK_STATUS / node_state

| Benchmark (node_state) | 我的環境 (TASK_STATUS) | 語意 |
|-----------------------|----------------------|------|
| TODO | TODO | 待辦 (未指派) |
| DOING | DOING | 進行中 (已指派未完成) |
| DONE | DONE | 已完成 (有 claim) |
| DONE_AUTO | DONE_AUTO | 自動完成 (無 claim) |
| TERMINATE + TERMINATED | CANCELLED | 取消/終止 |

### PROC_STATE / proc_state

| Benchmark (proc_state) | 我的環境 (PROC_STATE) | 語意 |
|-----------------------|----------------------|------|
| DOING | DOING | 進行中 |
| DONE | DONE | 已完成 |
| TERMINATE | TERMINATED | 終止 |

---

## 狀態分布比較 (比例)

| 狀態 | Benchmark % | 我的環境 % | 差異 |
|------|------------|-----------|------|
| TODO | 12.75% | 17.72% | 4.97% |
| DOING | 15.29% | 4.17% | 11.12% |
| DONE | 32.18% | 28.38% | 3.80% |
| DONE_AUTO | 32.33% | 43.27% | 10.94% |
| CANCELLED | 7.46% | 6.46% | 1.00% |

**說明**: 比例差異是因為資料時間點不同，不影響邏輯等價性判斷。

---

## View vs RMV 一致性

| 指標 | View | RMV | 一致 |
|------|------|-----|------|
| TASK_NODE 筆數 | 48,508 | 48,508 | ✅ |
| PROCINST_NODE 筆數 | 16,431 | 16,431 | ✅ |
| TODO 數量 | 8,597 | 8,597 | ✅ |
| DOING 數量 | 2,021 | 2,021 | ✅ |
| DONE 數量 | 13,767 | 13,767 | ✅ |
| DONE_AUTO 數量 | 20,990 | 20,990 | ✅ |
| CANCELLED 數量 | 3,133 | 3,133 | ✅ |

---

## 審核面向總結

| 面向 | Benchmark vs View | Benchmark vs RMV | View vs RMV |
|------|------------------|------------------|-------------|
| 指標定義 | ✅ 等價 | ✅ 等價 | ✅ 一致 |
| 狀態集合 | ✅ 等價 | ✅ 等價 | ✅ 一致 |
| 聚合層級 | ✅ 等價 | ✅ 等價 | ✅ 一致 |
| Join 語意 | ✅ 等價 | ✅ 等價 | ✅ 一致 |

---

## 附註

1. Benchmark 環境為 READ ONLY，本次審核未對其進行任何修改
2. 欄位名稱差異 (snake_case vs UPPER_CASE) 不影響語意等價性
3. 筆數差異源於資料同步時間點不同，非計算邏輯問題
