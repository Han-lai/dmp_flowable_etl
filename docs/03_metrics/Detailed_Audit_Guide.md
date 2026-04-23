# DMP 任務明細稽核指南 (Detailed Audit Guide)

本文件整合了 DMP Flowable 系統的數據稽核原理、操作指南與歷史對帳數據，作為跨系統數據比對的單一事實來源。

---

## 1. 稽核背景與數據原理

本系統採用 **獎牌管線架構 (Medallion Architecture)**，數據經過 Bronze (落地) → Silver (清洗) → Gold (物理化快照) 三層轉換。

### 1.1 金層快照展開機制 (Gold Layer Milestone Expansion)

根據金層實作規格（`sql/etl/dml/backfill_gold_milestone.sql`），每一筆任務會依據其生命週期內的 **三個非 NULL 時間點** 展開為快照列：

| 時間點 | 欄位 | Gold 狀態條件 |
| :--- | :--- | :--- |
| 任務開始 (Start) | `task_start_date` | snapshot_date < COALESCE(claim, end, tomorrow) → **Todo** |
| 任務認領 (Claim) | `task_claim_date` | claim ≤ snapshot_date < end → **Doing** |
| 任務結束 (End) | `task_end_date` | snapshot_date ≥ end → **Done** |

**關鍵特性**：
- Silver 層以 `NULLIF` 將未發生的 claim/end 轉為 `NULL`（非 epoch）。
- Gold 的 ARRAY JOIN 僅在任務有事件的日期建立快照，不對每天都建立。
- 因此同一筆任務在不同快照日可能分別計入 Todo、Doing、Done 三個 Bitmap，週/月彙總為 **各狀態 Bitmap 聯集**，而非各狀態互斥計數。

### 1.2 UI 與 Gold 彙總差異說明

| 彙總粒度 | Gold 計算方式 | UI 計算方式 | 預期行為 |
| :--- | :--- | :--- | :--- |
| **日** | 當日各狀態 Bitmap 計數 | 相同 | 應一致 |
| **週/月** | 週期內各狀態 Bitmap **聯集** | 週期末最終狀態（推測） | **必然差異** |

週/月層級的 Gold Todo/Doing/Acc 遠大於 UI，是因為 Gold 將整個週期內曾處於該狀態的任務全部聯集，而非只看週期末的狀態快照。**日級別的比對才是有效的跨系統驗證基礎。**

> **排除規則與 Vx 分類定義**：ClickHouse 端的完整排除條件（bypass / system_node / Q_order / R_order / notify_task / dummy_task）及 Vx 版本歸屬邏輯，詳見 [ETL_Transformation_Pipeline.md](ETL_Transformation_Pipeline.md) §3.3（Vx）及 §3.5（排除規則）。以下對帳均以 `is_excluded = 0` 為前提。

---

## 2. 稽核工具操作說明

### 方法一：使用 ClickHouse SQL 指令 (快速查詢)

> **注意**：Silver 層透過 `NULLIF(toDate(...), toDate('1970-01-01'))` 將未發生的時間欄位儲存為 `NULL`，查詢條件須使用 `IS NULL` / `IS NOT NULL`。

**查詢 Done（結案）任務**：快照日當天結案的任務。

```sql
SELECT
    task_id, task_start_time, task_claim_time, task_end_time,
    task_start_date, task_claim_date, task_end_date, task_primary_date,
    task_create_date, task_status, vx_type,
    region, plant, factory, line,
    region_source, plant_source, factory_source, line_source,
    is_excluded, exclude_reason,
    assignee_code, assignee_name,
    task_definition_key, task_name, mo_number, proc_inst_id,
    _mview_update_time
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3'
  AND task_end_date IS NOT NULL
  AND task_end_date = '2025-12-25'
ORDER BY task_end_time DESC;
```

**查詢 Todo（待認領）任務**：快照日當天啟動、尚未認領的任務。

```sql
SELECT task_id, task_start_time, task_claim_time, task_end_time,
    task_start_date, task_claim_date, task_end_date, task_primary_date,
    task_create_date, task_status, vx_type,
    region, plant, factory, line,
    region_source, plant_source, factory_source, line_source,
    is_excluded, exclude_reason, assignee_code, assignee_name,
    task_definition_key, task_name, mo_number, proc_inst_id, _mview_update_time
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3'
  AND task_start_date = '2025-12-25'
  AND COALESCE(task_claim_date, task_end_date, toDate('9999-12-31')) > '2025-12-25'
ORDER BY task_start_time DESC;
```

**查詢 Doing（進行中）任務**：快照日已認領、尚未結案的任務。

```sql
SELECT task_id, task_start_time, task_claim_time, task_end_time,
    task_start_date, task_claim_date, task_end_date, task_primary_date,
    task_create_date, task_status, vx_type,
    region, plant, factory, line,
    region_source, plant_source, factory_source, line_source,
    is_excluded, exclude_reason, assignee_code, assignee_name,
    task_definition_key, task_name, mo_number, proc_inst_id, _mview_update_time
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3'
  AND (task_start_date = '2025-12-25' OR task_claim_date = '2025-12-25')
  AND task_claim_date IS NOT NULL AND task_claim_date <= '2025-12-25'
  AND (task_end_date IS NULL OR task_end_date > '2025-12-25')
ORDER BY task_claim_time DESC;
```

**日級別 Gold 計數驗證（一次查三個狀態）**：

```sql
SELECT
    countIf(task_end_date IS NOT NULL AND task_end_date = '2025-12-25') AS done,
    countIf(task_start_date = '2025-12-25' AND COALESCE(task_claim_date, task_end_date, toDate('9999-12-31')) > '2025-12-25') AS todo,
    countIf((task_start_date = '2025-12-25' OR task_claim_date = '2025-12-25')
        AND task_claim_date IS NOT NULL AND task_claim_date <= '2025-12-25'
        AND (task_end_date IS NULL OR task_end_date > '2025-12-25')) AS doing
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3';
```

### 方法二：使用 Python 稽核腳本 (產出完整 CSV)

腳本位址：`scripts/etl/audit_done_details.py`

```bash
# Done（預設）
python scripts/etl/audit_done_details.py --date "2025-12-25" --region CNE --plant WJ2 --factory NBU --line E5 --vx V3

# Todo
python scripts/etl/audit_done_details.py --date "2025-12-25" --region CNE --plant WJ2 --factory NBU --line E5 --vx V3 --status todo

# Doing
python scripts/etl/audit_done_details.py --date "2025-12-25" --region CNE --plant WJ2 --factory NBU --line E5 --vx V3 --status doing

# All（任一時間點觸碰快照日）
python scripts/etl/audit_done_details.py --date "2025-12-25" --region CNE --plant WJ2 --factory NBU --line E5 --vx V3 --status all
```

`--status` 支援 `done`（預設）、`todo`、`doing`、`all`，CSV 輸出至 `scratch/audit_{status}_{region}_{plant}_{factory}_{line}_{date}.csv`。

---

## 3. Gold 層 vs UI 對帳結果 (2025-12-25 ~ 2025-12-31)

> **對帳基準**：UI 數據來源 `sql/rightdata_dmp_ui.md`；Gold 數據由 `gold.rmv_l5_task_completion` 查詢。  
> **有效對帳粒度**：**日級別**。週/月彙總因計算邏輯不同（Bitmap 聯集 vs 期末快照），必然存在差異，不作為異常依據。

### 3.1 CNE / WJ2 / NBU / E5 (V3) — 日級別

| 日期 | 指標 | Gold (A) | UI (B) | 差異 (A-B) | 狀態 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **12-25** | Todo | 26 | 26 | 0 | ✅ |
| **12-25** | Doing | 1 | 1 | 0 | ✅ |
| **12-25** | Done | **167** | 165 | **+2** | ⚠️ |
| **12-25** | Total | **194** | 192 | **+2** | ⚠️ |
| **12-25** | Acc | 40 | 40 | 0 | ✅ |
| **12-26** | Todo | 56 | 56 | 0 | ✅ |
| **12-26** | Doing | 12 | 12 | 0 | ✅ |
| **12-26** | Done | **84** | 80 | **+4** | ⚠️ |
| **12-26** | Total | **152** | 148 | **+4** | ⚠️ |
| **12-26** | Acc | 76 | 76 | 0 | ✅ |
| **12-27** | Todo | 14 | 14 | 0 | ✅ |
| **12-27** | Doing | 4 | 4 | 0 | ✅ |
| **12-27** | Done | **93** | 92 | **+1** | ⚠️ |
| **12-27** | Total | **111** | 110 | **+1** | ⚠️ |
| **12-27** | Acc | 44 | 44 | 0 | ✅ |
| **12-28** | Todo | 3 | 3 | 0 | ✅ |
| **12-28** | Doing | 0 | 0 | 0 | ✅ |
| **12-28** | Done | 8 | 8 | 0 | ✅ |
| **12-28** | Total | 11 | 11 | 0 | ✅ |
| **12-28** | Acc | 46 | 46 | 0 | ✅ |
| **12-29** | Todo | 3 | 3 | 0 | ✅ |
| **12-29** | Doing | 22 | 22 | 0 | ✅ |
| **12-29** | Done | **65** | 63 | **+2** | ⚠️ |
| **12-29** | Total | **90** | 88 | **+2** | ⚠️ |
| **12-29** | Acc | 40 | 40 | 0 | ✅ |
| **12-30** | Todo | 8 | 8 | 0 | ✅ |
| **12-30** | Doing | 60 | 60 | 0 | ✅ |
| **12-30** | Done | **206** | 194 | **+12** | ⚠️ |
| **12-30** | Total | **274** | 262 | **+12** | ⚠️ |
| **12-30** | Acc | 95 | 95 | 0 | ✅ |
| **12-31** | Todo | 9 | 9 | 0 | ✅ |
| **12-31** | Doing | 5 | 5 | 0 | ✅ |
| **12-31** | Done | **197** | 196 | **+1** | ⚠️ |
| **12-31** | Total | **211** | 210 | **+1** | ⚠️ |
| **12-31** | Acc | 97 | 97 | 0 | ✅ |

**CNE/WJ2/NBU/E5 差異模式**：
- Todo、Doing、Acc **全部吻合**。
- Done 每日 Gold 多出 **1–12 筆**，差距較小（最大 12-30 多 12 筆）。
- 12-28 全部吻合（當日活動量最少）。

---

### 3.2 CNS / DG3 / SMT / ST02 (V3) — 日級別

| 日期 | 指標 | Gold (A) | UI (B) | 差異 (A-B) | 狀態 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **12-25** | Todo | 66 | 66 | 0 | ✅ |
| **12-25** | Doing | 36 | 36 | 0 | ✅ |
| **12-25** | Done | **259** | 163 | **+96** | 🔴 |
| **12-25** | Total | **361** | 265 | **+96** | 🔴 |
| **12-25** | Acc | 154 | 154 | 0 | ✅ |
| **12-26** | Todo | 19 | 19 | 0 | ✅ |
| **12-26** | Doing | 66 | 66 | 0 | ✅ |
| **12-26** | Done | **124** | 91 | **+33** | 🔴 |
| **12-26** | Total | **209** | 176 | **+33** | 🔴 |
| **12-26** | Acc | 171 | 171 | 0 | ✅ |
| **12-27** | Todo | 22 | 22 | 0 | ✅ |
| **12-27** | Doing | 29 | 29 | 0 | ✅ |
| **12-27** | Done | **256** | 184 | **+72** | 🔴 |
| **12-27** | Total | **307** | 235 | **+72** | 🔴 |
| **12-27** | Acc | 94 | 94 | 0 | ✅ |
| **12-28** | Todo | 1 | 1 | 0 | ✅ |
| **12-28** | Doing | 1 | 1 | 0 | ✅ |
| **12-28** | Done | 10 | 10 | 0 | ✅ |
| **12-28** | Total | 12 | 12 | 0 | ✅ |
| **12-28** | Acc | 90 | 90 | 0 | ✅ |
| **12-29** | Todo | 64 | 64 | 0 | ✅ |
| **12-29** | Doing | 28 | 28 | 0 | ✅ |
| **12-29** | Done | **98** | 55 | **+43** | 🔴 |
| **12-29** | Total | **190** | 147 | **+43** | 🔴 |
| **12-29** | Acc | 132 | 132 | 0 | ✅ |
| **12-30** | Todo | 7 | 7 | 0 | ✅ |
| **12-30** | Doing | 53 | 53 | 0 | ✅ |
| **12-30** | Done | **75** | 67 | **+8** | ⚠️ |
| **12-30** | Total | **135** | 127 | **+8** | ⚠️ |
| **12-30** | Acc | 99 | 99 | 0 | ✅ |
| **12-31** | Todo | 3 | 3 | 0 | ✅ |
| **12-31** | Doing | 8 | 8 | 0 | ✅ |
| **12-31** | Done | **41** | 38 | **+3** | ⚠️ |
| **12-31** | Total | **52** | 49 | **+3** | ⚠️ |
| **12-31** | Acc | 65 | 65 | 0 | ✅ |

**CNS/DG3/SMT/ST02 差異模式**：
- Todo、Doing、Acc **全部吻合**。
- Done 差異顯著，12-25 多 **96 筆**、12-27 多 **72 筆**、12-29 多 **43 筆**。
- 12-28 全部吻合。

#### DG3 12-25 超額任務分佈（task_definition_key 統計）

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

---

### 3.3 週/月彙總對比（參考用，非有效驗證層級）

> 週/月彙總差異是 **設計預期行為**，不代表數據錯誤。Gold 使用 Bitmap 聯集計算跨日唯一任務數，UI 使用期末狀態聚合，兩者計算語義不同。

**CNE / WJ2 / NBU / E5 (V3)**

| 週期 | 指標 | Gold | UI | 差異 |
| :--- | :--- | :---: | :---: | :---: |
| Dec | Total | 2424 | 2294 | +130 |
| Dec | Done | 2319 | 2189 | +130 |
| W51 | Total | 571 | 502 | +69 |
| W51 | Done | 540 | 471 | +69 |
| W52 | Total | 621 | 583 | +38 |
| W52 | Done | 575 | 537 | +38 |

**CNS / DG3 / SMT / ST02 (V3)**

| 週期 | 指標 | Gold | UI | 差異 |
| :--- | :--- | :---: | :---: | :---: |
| Dec | Total | 4867 | 3555 | +1312 |
| Dec | Done | 4679 | 3373 | +1306 |
| W51 | Total | 740 | 412 | +328 |
| W51 | Done | 622 | 321 | +301 |
| W52 | Total | 1055 | 687 | +368 |
| W52 | Done | 964 | 597 | +367 |

---

### 3.4 CNE / WJ2 / NBU / E5 (V3) — 2025 年 11 月

對帳時間區間：2025-11-24 ~ 2025-11-30

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

---

### 3.5 CNS / DG3 / SMT / ST02 (V3) — 2025 年 11 月（差距最大）

對帳時間區間：2025-11-24 ~ 2025-11-30

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

#### 11-24 Doing 任務分佈（Gold=162 筆，UI=154 筆，差 +8）

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

## 4. 差異分析與待釐清項目

### 4.1 差異模式總結（11 月 + 12 月合併）

| 項目 | CNE/WJ2/NBU/E5 | CNS/DG3/SMT/ST02 |
| :--- | :--- | :--- |
| Todo（日） | ✅ 完全一致 | ✅ 完全一致 |
| Doing（日） | ✅ 完全一致 | ✅ 完全一致（11-24 除外，+8） |
| Acc（日） | ✅ 完全一致 | ✅ 完全一致 |
| Done（日） | ⚠️ Gold 多 1–18 筆 | 🔴 Gold 多 3–146 筆 |
| 休息日（所有指標） | ✅ 完全一致 | ✅ 完全一致 |

### 4.2 CNS Done 差異根本原因假設

CNS/DG3/SMT/ST02 的 Done 差距遠大於 CNE（最大 +146 vs +18），可能原因：

1. **UI 過濾條件**：UI 可能對 ST02 線體有額外的機台/工序過濾，僅顯示特定 `task_definition_key` 前綴的任務。
2. **MDM 維度殘留問題**：歷史上 ST02 曾有異廠同名（WJ5 vs DG3）的對應錯誤，已修復但可能有部分邊緣資料仍帶舊維度。
3. **Vx 分類邊界**：V3 工單前綴判定邏輯在 DG3 廠區較 WJ2 複雜，Gold 可能多計算了部分交界工單。

### 4.3 問題優先級彙整（依差異筆數排序）

#### CNS / DG3 / SMT / ST02（差距大，優先確認）

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

#### CNE / WJ2 / NBU / E5（差距小，次要確認）

| 優先 | 日期 | ClickHouse Done | UI Done | 差異 | 稽核明細 CSV |
| :---: | :--- | :---: | :---: | :---: | :--- |
| 1 | 2025-11-29 | 115 | 97 | **+18** | `scratch/audit_done_CNE_WJ2_NBU_E5_2025-11-29.csv` |
| 2 | 2025-12-30 | 206 | 194 | **+12** | `scratch/audit_done_CNE_WJ2_NBU_E5_2025-12-30.csv` |
| 3 | 2025-11-28 | 172 | 160 | **+12** | `scratch/audit_done_CNE_WJ2_NBU_E5_2025-11-28.csv` |
| 4 | 2025-11-24 | 451 | 442 | **+9** | `scratch/audit_done_CNE_WJ2_NBU_E5_2025-11-24.csv` |
| 5 | 2025-12-26 | 84 | 80 | **+4** | `scratch/audit_done_CNE_WJ2_NBU_E5_2025-12-26.csv` |

### 4.4 下一步行動

- [ ] 優先查 CNS 11-24（+146）與 12-25（+96）：差距最大，最能暴露 UI 的額外過濾條件
- [ ] 確認 UI 是否有隱含的 `task_definition_key` 前綴過濾條件
- [ ] 確認 11-24 Doing 差異（+8）為特例，UI Doing 的日期範圍定義是否有異
- [ ] CNE 的差距為 CNS 的縮小版，若 CNS 根因確認後，CNE 應可套用相同解釋

---

## 5. 稽核明細抽樣範例 (WJ2 E5, 2025-12-25)

根據 2025-12-25 的稽核結果，當天共有 **167 筆** 結案任務，以下為部分明細特徵：

| Task ID | Task Name | Start Time | End Time | Status |
| :--- | :--- | :--- | :--- | :--- |
| `219710d2-def4-11f0-86aa-4ed4e1f8f5a1` | MFG Materials feeding | 2025-12-22 13:07:36 | 2025-12-25 15:21:50 | DONE |
| `990cefb8-dd71-11f0-ba03-024335f9cdd9` | MFG Generates Material Plan | 2025-12-20 15:00:41 | 2025-12-25 15:21:38 | DONE |
| `012b37c1-e12e-11f0-ba03-024335f9cdd9` | MFG Checks WO OI | 2025-12-25 09:05:12 | 2025-12-25 10:20:18 | DONE |

---

*文件更新日期: 2026-04-23*
