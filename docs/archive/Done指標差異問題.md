# 資料問題

---

## 背景：ClickHouse 現行排除條件說明

在提出差異問題之前，先列出 **ClickHouse Silver 層已套用的所有排除規則**（`is_excluded = 1`），這些任務**不計入任何指標**。稽核查詢中統一加上 `WHERE is_excluded = 0`。

### 排除規則一覽（`silver.mv_fact_task_vx`）

| 規則 | 條件 | `exclude_reason` 標記 |
| :--- | :--- | :--- |
| **旁路節點（Bypass）** | 任務帶有 `autoComplete = 1` 的流程變數 | `bypass` |
| **系統節點（E 前綴）** | `task_definition_key LIKE 'E%'` | `system_node` |
| **系統節點（C 前綴）** | `task_definition_key LIKE 'C%'` | `system_node` |
| **Q 類工單** | `mo_number LIKE 'Q%'` | `Q_order` |
| **R 類工單** | `mo_number LIKE 'R%'` | `R_order` |
| **通知類任務** | `task_name LIKE '%Notify%'` | `notify_task` |
| **虛擬任務** | `task_name LIKE '%Dummy%'` | `dummy_task` |

#### 排除條件 SQL（`sql/etl/dml/backfill_silver.sql`）

```sql
-- is_excluded 旗標
multiIf(
    tb.LONG_ = 1,                                                              1,  -- bypass
    (t.TASK_DEF_KEY_ LIKE 'E%') OR (t.TASK_DEF_KEY_ LIKE 'C%'),              1,  -- system_node
    (COALESCE(v_pivot.varinst_moNumber, '') LIKE 'Q%')
        OR (COALESCE(v_pivot.varinst_moNumber, '') LIKE 'R%'),                1,  -- Q/R_order
    (t.NAME_ LIKE '%Notify%') OR (t.NAME_ LIKE '%Dummy%'),                   1,  -- notify/dummy
    0
) AS is_excluded,

-- exclude_reason 文字標記
multiIf(
    tb.LONG_ = 1,                                              'bypass',
    t.TASK_DEF_KEY_ LIKE 'E%',                                'system_node',
    t.TASK_DEF_KEY_ LIKE 'C%',                                'system_node',
    COALESCE(v_pivot.varinst_moNumber, '') LIKE 'Q%',         'Q_order',
    COALESCE(v_pivot.varinst_moNumber, '') LIKE 'R%',         'R_order',
    t.NAME_ LIKE '%Notify%',                                   'notify_task',
    t.NAME_ LIKE '%Dummy%',                                    'dummy_task',
    ''
) AS exclude_reason
```

> `tb.LONG_ = 1` 來源：`bronze.bpm_act_hi_varinst` 中 `NAME_ = 'autoComplete'` 且 `LONG_ = 1`，代表旁路節點。

### Vx 版本分類規則（`vx_type`）

| 優先順序 | 條件 | 分類結果 |
| :---: | :--- | :--- |
| 1 | `mo_number` 前三碼 ∈ `{196, 199, 200, 210, 212, 213}` | `V1` |
| 2 | `task_definition_key LIKE 'V1%'` | `V1` |
| 3 | `task_definition_key LIKE 'V2%'` | `V2` |
| 4 | `task_definition_key LIKE 'V3%'` | `V3` |
| 5 | 其餘 | `Unknown` |

#### Vx 分類 SQL（`sql/etl/dml/backfill_silver.sql`）

```sql
CASE
    -- 規則 1: 特定工單號前綴 → 強制 V1
    WHEN substring(COALESCE(v_pivot.varinst_moNumber, ''), 1, 3)
         IN ('196', '199', '200', '210', '212', '213')
    THEN 'V1'
    -- 規則 2-4: TASK_DEF_KEY_ 前綴匹配
    WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
    WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
    WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
    -- 規則 5: 預設
    ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
END AS vx_type
```

> **規則 1 優先級最高**：工單號前綴 196/199/200/210/212/213 的任務即使 `TASK_DEF_KEY_` 以 `V3_` 開頭，仍強制歸類為 V1。

> **以上是 ClickHouse 端已套用的過濾邏輯。以下差異問題的前提是：兩端排除規則應相同。若 UI 有額外排除條件，請說明。**

---

## 1. Done 任務數：ClickHouse 計算值高於 UI 顯示值（CNE / WJ2 / NBU / E5）

### 問題敘述

對帳時間區間：2025-12-25 ~ 2025-12-31，條件：V3 / CNE / WJ2 / NBU / E5

以下為 **日級別** 的 Done 任務數比對。Todo、Doing、Acc 三個指標與 UI **完全一致**，但 Done 每日有 1～12 筆差距。

| 日期 | ClickHouse (Gold) | UI | 差異 |
| :--- | :---: | :---: | :---: |
| 2025-12-25 | **167** | 165 | +2 |
| 2025-12-26 | **84** | 80 | +4 |
| 2025-12-27 | **93** | 92 | +1 |
| 2025-12-28 | 8 | 8 | 0 ✅ |
| 2025-12-29 | **65** | 63 | +2 |
| 2025-12-30 | **206** | 194 | +12 |
| 2025-12-31 | **197** | 196 | +1 |

### 確認問題

> **ClickHouse 的 Done 定義**：`task_end_date = 查詢日期`，且任務未被排除（`is_excluded = 0`）。
>
> **請確認 UI 是否有以下任一額外過濾條件，導致 Done 數量偏低？**
> 1. 特定 `task_definition_key` 前綴白名單或黑名單？
> 2. 特定 `mo_number` 工單號段過濾？
> 3. 任務時長或其他業務規則排除？

### ClickHouse 查詢語法（可重現）

以 2025-12-25 為例：

```sql
SELECT
    task_id,
    task_start_time,
    task_claim_time,
    task_end_time,
    task_start_date,
    task_claim_date,
    task_end_date,
    task_status,
    vx_type,
    task_definition_key,
    task_name,
    mo_number,
    is_excluded,
    exclude_reason
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3'
  AND task_end_date IS NOT NULL
  AND task_end_date = '2025-12-25'
ORDER BY task_end_time DESC;
```

> 完整明細 CSV 位於：`scratch/audit_done_CNE_WJ2_NBU_E5_2025-12-25.csv`（167 筆）

---

## 2. Done 任務數：ClickHouse 計算值高於 UI 顯示值（CNS / DG3 / SMT / ST02）⚠️ 差距較大

### 問題敘述

對帳時間區間：2025-12-25 ~ 2025-12-31，條件：V3 / CNS / DG3 / SMT / ST02

CNS 產線的 Done 差距明顯大於 CNE，最高單日差距達 **96 筆**（2025-12-25）。同樣地，Todo、Doing、Acc **與 UI 完全一致**，差距集中在 Done。

| 日期 | ClickHouse (Gold) | UI | 差異 |
| :--- | :---: | :---: | :---: |
| 2025-12-25 | **259** | 163 | **+96** |
| 2025-12-26 | **124** | 91 | **+33** |
| 2025-12-27 | **256** | 184 | **+72** |
| 2025-12-28 | 10 | 10 | 0 ✅ |
| 2025-12-29 | **98** | 55 | **+43** |
| 2025-12-30 | **75** | 67 | +8 |
| 2025-12-31 | **41** | 38 | +3 |

### 確認問題

> **與問題 1 相同的確認需求**，另外請額外確認：
>
> 1. UI 對 ST02 線體是否有 **廠區限縮**（例如只顯示 DG3 廠的 ST02，而非 WJ5 廠的同名線體）？
> 2. ClickHouse 已針對「異廠同名線體」以 `PlantCode` 複合鍵修正，但 UI 側是否有類似的修正？
> 3. 如果 UI 的 Done = 163，請提供 **UI 所使用的 SQL 或查詢條件**，以利我們比對超額的 96 筆任務屬於哪一類。

### ClickHouse 查詢語法（可重現）

以 2025-12-25 為例：

```sql
SELECT
    task_id,
    task_start_time,
    task_claim_time,
    task_end_time,
    task_start_date,
    task_claim_date,
    task_end_date,
    task_status,
    vx_type,
    task_definition_key,
    task_name,
    mo_number,
    is_excluded,
    exclude_reason
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND region = 'CNS' AND plant = 'DG3' AND factory = 'SMT' AND line = 'ST02' AND vx_type = 'V3'
  AND task_end_date IS NOT NULL
  AND task_end_date = '2025-12-25'
ORDER BY task_end_time DESC;
```

> 完整明細 CSV 位於：`scratch/audit_done_CNS_DG3_SMT_ST02_2025-12-25.csv`（259 筆）

### 超額任務分佈（task_definition_key 統計）

以下為 2025-12-25 的 Done 任務（共 259 筆）按 `task_definition_key` 前綴分佈，供確認 UI 是否有前綴白名單或過濾規則：

| task_definition_key 前綴 | ClickHouse 筆數 |
| :--- | :---: |
| V3_5_2_1 | 53 |
| V3_5_2_4 | 39 |
| V3_5_4_3 | 38 |
| V3_5_1_1 | 35 |
| V3_5_1_2 | 30 |
| V3_5_1_9 | 15 |
| V3_5_3_4 | 9 |
| V3_5_2_5 | 7 |
| V3_5_3_2 | 5 |
| V3_5_4_1 | 5 |
| V3_5_2_9 | 5 |
| V3_5_2_6 | 4 |
| V3_5_4_4 | 4 |
| V3_5_3_8 | 3 |
| V3_5_4_2 | 3 |
| V3_5_1_8 | 2 |
| V3_5_3_7 | 1 |
| V3_5_1_6 | 1 |
| **合計** | **259** |

> **請確認**：UI 顯示 163 筆，差距 96 筆。上表中哪些前綴或任務類型不應計入 Done？

---

## 3. Done 任務數差異（CNE / WJ2 / NBU / E5）— 2025 年 11 月

### 問題敘述

對帳時間區間：2025-11-24 ~ 2025-11-30，條件：V3 / CNE / WJ2 / NBU / E5

| 日期 | ClickHouse Done | UI Done | 差異 | ClickHouse Todo | UI Todo | ClickHouse Doing | UI Doing | ClickHouse Acc | UI Acc |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2025-11-24 | **451** | 442 | **+9** | 11 | 11 | 108 | 108 | 146 | 146 |
| 2025-11-25 | 101 | 101 | 0 | 5 | 5 | 7 | 7 | 116 | 116 |
| 2025-11-26 | 142 | 142 | 0 | 2 | 2 | 1 | 1 | 78 | 78 |
| 2025-11-27 | 106 | 106 | 0 | 4 | 4 | 7 | 7 | 58 | 58 |
| 2025-11-28 | **172** | 160 | **+12** | 12 | 12 | 19 | 19 | 68 | 68 |
| 2025-11-29 | **115** | 97 | **+18** | 7 | 7 | 38 | 38 | 65 | 65 |
| 2025-11-30 | 8 | 8 | 0 | 4 | 4 | 0 | 0 | 68 | 68 |

- **差異模式**：與 12 月相同，Todo / Doing / Acc 完全吻合，Done 僅部分日期有差距（11-25 ~ 11-27、11-30 完全吻合）。
- 完整明細 CSV：`scratch/audit_done_CNE_WJ2_NBU_E5_2025-11-{24,28,29}.csv`

---

## 4. Done / Doing 任務數差異（CNS / DG3 / SMT / ST02）— 2025 年 11 月（差距最大）

### 問題敘述

對帳時間區間：2025-11-24 ~ 2025-11-30，條件：V3 / CNS / DG3 / SMT / ST02

| 日期 | ClickHouse Done | UI Done | 差異(Done) | ClickHouse Doing | UI Doing | 差異(Doing) | ClickHouse Acc | UI Acc |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2025-11-24 | **230** | 84 | **+146** | **162** | 154 | **+8** | 283 | 283 |
| 2025-11-25 | **240** | 167 | **+73** | 78 | 78 | 0 | 320 | 320 |
| 2025-11-26 | **48** | 39 | **+9** | 10 | 10 | 0 | 306 | 306 |
| 2025-11-27 | 42 | 42 | 0 | 11 | 11 | 0 | 275 | 275 |
| 2025-11-28 | **100** | 97 | **+3** | 22 | 22 | 0 | 265 | 265 |
| 2025-11-29 | **154** | 134 | **+20** | 100 | 100 | 0 | 184 | 184 |
| 2025-11-30 | **46** | 29 | **+17** | 0 | 0 | 0 | 211 | 211 |

- **11-24 異常**：Done 差距達 **+146 筆**（Gold=230, UI=84），且 Doing 也有 +8 筆差距。這是所有對帳數據中最大的單日差異。
- **Todo / Acc 全部吻合**（7 天均無差距）。
- 完整明細 CSV：`scratch/audit_done_CNS_DG3_SMT_ST02_2025-11-{24,25,29,30}.csv`

### 確認問題（11-24 專項）

> 2025-11-24 CNS/ST02 的 Done 差距 **+146 筆**，遠超其他日期。請確認：
>
> 1. 11-24（星期一）是否為節假日或特殊排班，導致 UI 有額外的日期過濾？
> 2. Doing 也同時多出 +8 筆，與其他日期的模式不同（其他日期 Doing 均完全吻合）。請確認 UI 的 Doing 定義是否有日期範圍限制？

### 11-24 Doing 任務分佈（Gold=162 筆，UI=154 筆，差 +8）

| task_definition_key 前綴 | ClickHouse 筆數 |
| :--- | :---: |
| V3_5_1_1 | 63 |
| V3_5_2_1 | 54 |
| V3_5_2_6 | 8 |
| V3_5_2_3 | 7 |
| V3_5_2_7 | 7 |
| V3_5_2_8 | 5 |
| V3_5_4_1 | 4 |
| 其餘各 1-2 筆 | 14 |
| **合計** | **162** |

---

---

## 5. 問題優先級彙整（依差異筆數排序）

### CNS / DG3 / SMT / ST02（差距大，優先確認）

| 優先 | 日期 | ClickHouse Done | UI Done | 差異 | 稽核明細 CSV |
| :---: | :--- | :---: | :---: | :---: | :--- |
| 1 | 2025-11-24 | 230 | 84 | **+146** | `scratch/audit_done_CNS_DG3_SMT_ST02_2025-11-24.csv` |
| 2 | 2025-12-25 | 259 | 163 | **+96** | `scratch/audit_done_CNS_DG3_SMT_ST02_2025-12-25.csv` |
| 3 | 2025-11-25 | 240 | 167 | **+73** | `scratch/audit_done_CNS_DG3_SMT_ST02_2025-11-25.csv` |
| 4 | 2025-12-27 | 256 | 184 | **+72** | `scratch/audit_done_CNS_DG3_SMT_ST02_2025-12-27.csv` |
| 5 | 2025-12-29 | 98 | 55 | **+43** | `scratch/audit_done_CNS_DG3_SMT_ST02_2025-12-29.csv` |
| 6 | 2025-12-26 | 124 | 91 | **+33** | `scratch/audit_done_CNS_DG3_SMT_ST02_2025-12-26.csv` |
| 7 | 2025-11-29 | 154 | 134 | **+20** | `scratch/audit_done_CNS_DG3_SMT_ST02_2025-11-29.csv` |
| 8 | 2025-11-30 | 46 | 29 | **+17** | `scratch/audit_done_CNS_DG3_SMT_ST02_2025-11-30.csv` |
| 9 | 2025-11-28 | 100 | 97 | **+3** | `scratch/audit_done_CNS_DG3_SMT_ST02_2025-11-28.csv` |

> **特例：2025-11-24 同時有 Doing 差異（+8）**，為所有對帳日期中唯一 Doing 也不吻合的情形。
> Doing 明細：`scratch/audit_doing_CNS_DG3_SMT_ST02_2025-11-24.csv`

### CNE / WJ2 / NBU / E5（差距小，次要確認）

| 優先 | 日期 | ClickHouse Done | UI Done | 差異 | 稽核明細 CSV |
| :---: | :--- | :---: | :---: | :---: | :--- |
| 1 | 2025-11-29 | 115 | 97 | **+18** | `scratch/audit_done_CNE_WJ2_NBU_E5_2025-11-29.csv` |
| 2 | 2025-12-30 | 206 | 194 | **+12** | `scratch/audit_done_CNE_WJ2_NBU_E5_2025-12-30.csv` |
| 3 | 2025-11-28 | 172 | 160 | **+12** | `scratch/audit_done_CNE_WJ2_NBU_E5_2025-11-28.csv` |
| 4 | 2025-11-24 | 451 | 442 | **+9** | `scratch/audit_done_CNE_WJ2_NBU_E5_2025-11-24.csv` |
| 5 | 2025-12-26 | 84 | 80 | **+4** | `scratch/audit_done_CNE_WJ2_NBU_E5_2025-12-26.csv` |

### 查閱建議

1. **優先查 CNS 11-24（+146）與 12-25（+96）**：差距最大，最能暴露 UI 的額外過濾條件。
2. **CNE 的差距為 CNS 的縮小版**，若 CNS 根因確認後，CNE 應可套用相同解釋。
3. **11-24 Doing 差異為特例**：需額外確認 UI Doing 的日期範圍定義是否有異。

---

*文件建立日期: 2026-04-23*
*對帳資料來源: `sql/rightdata_dmp_ui.md`*
*ClickHouse 資料來源: `silver.mv_fact_task_vx`、`gold.rmv_l5_task_completion`*
