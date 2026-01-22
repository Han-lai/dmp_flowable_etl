# 規則實作快速參考表 (2026-01-22)

## 四大規則實作位置速查

### 規則一：V1/V2/V3 分類

| 項目 | 內容 |
|------|------|
| **規則定義** | L5 任務編號開頭分類：V1%, V2%, V3% |
| **實作檔案** | `sql/12_create_silver_mviews_layer2.sql` |
| **實作位置** | 第 45-48 行 |
| **SQL 邏輯** | `CASE WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1' ...` |
| **驗證狀態** | ✅ 文件與實作一致 |

---

### 規則二：工單 override（315% 規則）

| 項目 | 內容 |
|------|------|
| **規則定義** | 工單號以 196/199/200/210/212/213/315 開頭 → 歸類為 V1 |
| **實作檔案** | `sql/12_create_silver_mviews_layer2.sql` |
| **實作位置** | 第 45-52 行 |
| **修正前** | `IN ('3152600035', '3152600036', '3152600037')` |
| **修正後** | `LIKE '196%' OR ... OR LIKE '315%'` |
| **驗證狀態** | ✅ 已修正，文件與實作一致 |
| **修正日期** | 2026-01-22 |

---

### 規則三：Q/R 排除

| 項目 | 內容 |
|------|------|
| **規則定義** | 工單號以 Q 或 R 開頭 → 排除統計 |
| **實作檔案** | `sql/12_create_silver_mviews_layer2.sql` |
| **實作位置** | 第 95-99 行 |
| **SQL 邏輯** | `WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'Q%' OR ... LIKE 'R%' THEN 1` |
| **驗證狀態** | ✅ 文件與實作一致 |

---

### 規則四：NPE/MFG 細分

| 項目 | 內容 |
|------|------|
| **規則定義** | V1 任務再區分 NPE / MFG |
| **實作檔案** | `sql/12_create_silver_mviews_layer2.sql` |
| **實作位置** | 第 60-85 行 |
| **修正前** | 混用 `BUSINESS_KEY_ LIKE '%NPE%'` 和 `varinst_name LIKE '%NPE%'` |
| **修正後** | 統一使用 `varinst_name LIKE '%NPE%'` |
| **資料來源** | `bronze.bpm_act_hi_varinst` 表的 NAME_ 欄位 |
| **驗證狀態** | ✅ 已修正，文件與實作一致 |
| **修正日期** | 2026-01-22 |

---

## 資料來源速查表

### 工單號判斷

| 欄位 | 來源表 | 來源欄位 | 取得方式 |
|------|--------|---------|---------|
| moNumber | `APP_SRV_BPM.dbo.ACT_HI_VARINST` | `TEXT_` (NAME_='moNumber') | 轉置後取得 |

**轉置 SQL：**
```sql
SELECT 
    PROC_INST_ID_,
    MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
FROM ACT_HI_VARINST
WHERE NAME_ = 'moNumber'
GROUP BY PROC_INST_ID_
```

**Silver 層實現：** `silver.mv_varinst_pivoted` (L20)

---

### NPE 判別

| 欄位 | 來源表 | 來源欄位 | 判別邏輯 |
|------|--------|---------|---------|
| varinst_name | `APP_SRV_BPM.dbo.ACT_HI_VARINST` | `NAME_` (所有值) | `LIKE '%NPE%'` |

**Silver 層實現：** `silver.mv_varinst_pivoted` (L26)

```sql
arrayStringConcat(arrayDistinct(groupArray(NAME_)), ',') AS varinst_name
```

---

### V1/V2/V3 歸屬

| 欄位 | 來源表 | 來源欄位 | 判別邏輯 |
|------|--------|---------|---------|
| TaskDefinitionKey | `APP_SRV_BPM.dbo.ACT_HI_TASKINST` | `TASK_DEF_KEY_` | 前兩字元 (V1/V2/V3) |

---

## 優先級規則

### Vx 歸屬優先級（修正後）

```
優先級 1（最高）：工單號規則
  ├─ LIKE '196%' → V1
  ├─ LIKE '199%' → V1
  ├─ LIKE '200%' → V1
  ├─ LIKE '210%' → V1
  ├─ LIKE '212%' → V1
  ├─ LIKE '213%' → V1
  └─ LIKE '315%' → V1

優先級 2：TaskDefinitionKey 前綴
  ├─ LIKE 'V1%' → V1
  ├─ LIKE 'V2%' → V2
  └─ LIKE 'V3%' → V3

優先級 3（最低）：預設值
  └─ 前兩字元 → Vx
```

---

### V1 子類型判別優先級

```
優先級 1（最高）：工單號規則 + NPE 判別
  ├─ 工單號規則 + varinst_name LIKE '%NPE%' → V1_NPE
  └─ 工單號規則 + 其他 → V1_MFG

優先級 2：TaskDefinitionKey + NPE 判別
  ├─ TaskDefinitionKey LIKE 'V1%' + varinst_name LIKE '%NPE%' → V1_NPE
  └─ TaskDefinitionKey LIKE 'V1%' + 其他 → V1_MFG

優先級 3（最低）：其他
  └─ NULL
```

---

## 排除規則

### 排除條件（任務層級）

```
排除條件（任一符合即排除）：
├─ TaskBypass != 'N'
├─ TaskDefinitionKey LIKE 'E%'
├─ TaskDefinitionKey LIKE 'C%'
├─ moNumber LIKE 'Q%'
└─ moNumber LIKE 'R%'
```

**實作位置：** `sql/12_create_silver_mviews_layer2.sql` (L90-99)

---

## Factory 欄位定義

### 層級別 Factory 欄位

| 層級 | 表名 | 欄位名 | 來源 | 用途 |
|------|------|--------|------|------|
| **任務層級** | `mv_fact_task_vx_attribution` | `factory` | 流程變數 | 任務所屬製造區 |
| **員工層級** | `mv_emp_org_info` | `factory_code` | MDM 主檔 | 員工所屬製造區 |
| **聚合層級** | `mv_l5_metrics_realtime` | `factory` | 任務層級 | 指標聚合維度 |

---

## 常用查詢範例

### 查詢 V1 任務（包含工單號規則）

```sql
SELECT * FROM silver.mv_fact_task_vx_attribution
WHERE vx_type = 'V1'
  AND is_excluded = 0
```

### 查詢 V1_NPE 任務

```sql
SELECT * FROM silver.mv_fact_task_vx_attribution
WHERE vx_subtype = 'V1_NPE'
  AND is_excluded = 0
```

### 查詢被排除的任務及原因

```sql
SELECT 
    task_id,
    exclude_reason,
    COUNT(*) as count
FROM silver.mv_fact_task_vx_attribution
WHERE is_excluded = 1
GROUP BY exclude_reason
```

### 查詢工單號規則適用的任務

```sql
SELECT * FROM silver.mv_fact_task_vx_attribution
WHERE is_special_v1_rule = 1
  AND is_excluded = 0
```

---

## 文件參考

| 文件 | 內容 | 更新日期 |
|------|------|---------|
| `docs/metric_definitions.md` | 完整規則定義 + 資料來源說明 | 2026-01-22 |
| `docs/consistency_verification_report_2026_01_22.md` | 詳細驗證報告 | 2026-01-22 |
| `docs/rules_implementation_summary_2026_01_22.md` | 修正摘要 | 2026-01-22 |
| `docs/rules_quick_reference_2026_01_22.md` | 本文件 | 2026-01-22 |

---

**最後更新：** 2026-01-22  
**驗證狀態：** ✅ 完成
