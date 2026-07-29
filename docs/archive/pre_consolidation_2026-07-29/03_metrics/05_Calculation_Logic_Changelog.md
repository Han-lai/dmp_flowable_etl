# 指標計算邏輯版本異動記錄

> **文件性質**：正式技術規格文件（Formal Technical Specification）
>
> **維護規定**：每次調整任何指標的計算邏輯（ETL SQL、Gold Schema、Cube.js Measure），**必須**在本文件末尾追加一筆異動記錄。格式詳見 [§4 異動記錄模板](#4-異動記錄模板)。
>
> **文件位置**：`docs/03_metrics/05_Calculation_Logic_Changelog.md`
> **最後更新**：2026-06-11

---

## 目錄

1. [指標計算架構概觀](#1-指標計算架構概觀)
2. [核心邏輯演進總表](#2-核心邏輯演進總表)
3. [各版本詳細說明](#3-各版本詳細說明)
   - [V2 原版 (2026-04-02)](#31-v2-原版-2026-04-02)
   - [V3 Bitmap 架構 (2026-04-21)](#32-v3-bitmap-架構-2026-04-21)
   - [V4 Cohort 邏輯 (2026-04-28)](#33-v4-cohort-邏輯-2026-04-28)
   - [V4.2 多粒度結算 (2026-04-28)](#34-v42-多粒度結算-2026-04-28)
   - [V4.3 分母優化 (2026-05-07)](#35-v43-分母優化-2026-05-07)
   - [V4 Pre-aggregation 預聚合 (2026-05-27)](#36-v4-pre-aggregation-預聚合-2026-05-27)
   - [V4.4 Rate 指標修正 (2026-06-05)](#37-v44-rate-指標修正-2026-06-05)
   - [V3.1 歷史資料混合管線 (2026-06-10)](#38-v31-歷史資料混合管線-2026-06-10)
4. [異動記錄模板](#4-異動記錄模板)
5. [異動歷史](#5-異動歷史)

---

## 1. 指標計算架構概觀

### 1.0 兩大計算典範

L5 報表的計算邏輯歷經兩次典範轉移，形成截然不同的設計哲學：

| 典範 | 代號 | 核心概念 | 時間演進 |
|------|------|---------|---------|
| **Bitmap 事件日快照版** | Bitmap 典範 | 以「任務發生了什麼事件」為快照點，每個事件日各展開一筆；用 Bitmap 精確去重 | V2.0 → V3.0（已停用於新資料） |
| **Cohort 開單日固定版** | Cohort 典範 | 以「任務何時開出」為唯一快照點，狀態在週末/月底「結算」；資料不可變 | V4.0 起，現行生產標準 |

> **重要**：文件 §3 的「V3 Bitmap 架構」與現行架構圖裡的「歷史管線（2025-10~2026-03）」是不同概念，前者是開發演進階段的代號，後者是資料時間範圍的管線分界。

---

### 1.1 兩大典範核心差異

| 比較項目 | Bitmap 典範（已停用） | Cohort 典範（現行） |
|---------|---------------------|-------------------|
| **快照邏輯** | `ARRAY JOIN [start, claim, end]`，同一任務最多 3 筆 | `snapshot_date = task_start_date`，每任務唯一 1 筆 |
| **Day 狀態** | 隨時間漂移（今天 Todo，明天變 Doing） | 永久固定（開單日截面） |
| **Week 狀態** | 查詢當下的截面，歷史數字會變動 | 週末截面，一旦計算永不更動 |
| **Month 狀態** | 同上 | 月底截面，同上 |
| **去重方式** | `groupBitmapState(cityHash64(task_id))` | 同左（但快照點已固定，不再有漂移） |
| **歷史穩定性** | ❌ 今天看和昨天看數字不同 | ✅ 歷史數字永遠一致 |

---

### 1.2 現行雙管線架構（2026-06-11 起）

L5 報表以 `2026-04-01` 為分界，由兩條管線分別負責不同時間範圍的資料，最終統一輸出至同一張預聚合彙總表：

```
Silver (mv_fact_task_vx)
     │
     ├─── [歷史管線] task_start_date ＜ 2026-04-01 ─────────────────────────┐
     │    backfill_gold_summary_historical.sql                                            │
     │    典範：混合（Day 保留事件日語意；Week/Month 採 Cohort）              │
     │    ├─ Day:   事件日 ARRAY JOIN；acc 讀 rmv_l5_acc_phys 7D Bitmap      │
     │    ├─ Week:  Cohort + ISO 週鍵；toISOYear=toYear 排除 Dec 29-31       │
     │    └─ Month: Cohort 月底截面                                          │
     │                                                                        │
     └─── [現行管線] task_start_date ≥ 2026-04-01 ──────────────────────────┤
          典範：純 Cohort + Bitmap 中間層                                     │
          backfill_gold_milestone.sql → rmv_l5_task_completion_phys (Bitmap) │
          backfill_gold_acc.sql       → rmv_l5_acc_phys (Bitmap)             │
          backfill_gold_summary.sql   (Bitmap 解碼 → 整數)                   │
                                                                              ↓
                                                         gold.rmv_l5_task_summary
                                                         (預聚合整數彙總表，兩管線共用)
                                                                              │
                                                         Cube.js cube_l5_task_periodic.js
                                                         (sum() 查詢，無即時 Bitmap 運算)
```

### 1.3 各管線核心差異

| 項目 | 歷史管線（2025-10 ~ 2026-03） | 現行管線（2026-04 起） |
|------|------------------------------|----------------------|
| **SQL 入口** | `backfill_gold_summary_historical.sql` | `backfill_gold_milestone.sql` → `backfill_gold_summary.sql` |
| **計算典範** | **混合**（Day 事件日 + Week/Month Cohort） | **純 Cohort** |
| **中間層** | 無（直接輸出整數至 summary） | `rmv_l5_task_completion_phys`（Bitmap）、`rmv_l5_acc_phys` |
| **Day snapshot** | 事件日 ARRAY JOIN（task_start/claim/end） | 開單日唯一快照（task_start_date） |
| **Week 語意** | Cohort + ISO 週鍵，`toISOYear=toYear` 排除跨年 | Cohort + ISO 週鍵，週末截面 Bitmap |
| **Month 語意** | Cohort 月底截面（countIf） | Cohort 月底截面（Bitmap） |
| **Acc 來源（Day）** | `rmv_l5_acc_phys` 7D Bitmap（與現行管線相同） | `rmv_l5_acc_phys` 7D Bitmap |
| **Acc 來源（W/M）** | `countIf(todo) + countIf(doing)` | `bitmapOr(todo_weekly, doing_weekly)` |
| **輸出格式** | 整數（直接寫 gold.rmv_l5_task_summary） | 整數（Bitmap 解碼後寫入） |

### 1.3 Gold 彙總表結構（兩管線共用輸出）

```
gold.rmv_l5_task_summary (ReplacingMergeTree)
  period_type   String      -- 'Day' / 'Week' / 'Month'
  period_key    String      -- '2025-12-25' / '2025-W52' / '2025-12'
  snapshot_date Date        -- 用於時間索引
  period_name   String      -- '12/25' / 'W52' / 'Dec.'
  vx_type, region, plant, factory, line  String
  total_qty, todo_qty, doing_qty, done_qty, doing_done_qty  UInt32
  acc_qty, acc_total_qty                                     UInt32
  _refresh_time DateTime64(3)
```

### 1.4 Cube.js 查詢層（Layer 3）

```
cube_l5_task_periodic.js
  ├─ anchor_dt  = max(snapshot_date for Day in 選取日期範圍)
  ├─ Month block: period_key = formatDateTime(anchor_dt, '%Y-%m')
  ├─ Week block:  period_key IN (ISO週鍵 for anchor, anchor-7d, anchor-14d)
  └─ Day block:   snapshot_date BETWEEN anchor-6 AND anchor

accRate 公式:
  Day   → if(accQty ≥ accTotalQty, 100, floor(accQty*100/accTotalQty))
  Week/Month → floor((todoQty+doingQty)*100/totalQty)
```

**指標語意說明**

| 指標 | 定義 |
|------|------|
| **Total** | 該時間範圍內開出的任務總數 |
| **Todo** | 結算點時尚未被領取且未結案的任務 |
| **Doing** | 結算點時已被領取但尚未結案的任務 |
| **Done** | 結算點時已結案的任務 |
| **Acc (積壓)** | 過去 7 天內開出、且截至快照日仍未結案的任務集合 |
| **Acc Rate** | 積壓率 / 落後率（見各版本定義） |
| **Done Rate** | 結案率 = Done / Total |

---

## 2. 核心邏輯演進總表

### 2.1 snapshot_date 產生方式

| 版本 | 提交 | snapshot_date 產生邏輯 | 影響 |
|------|------|----------------------|------|
| V2 / V3 | `7c4bf44` / `21e6259` | `ARRAY JOIN [start, claim, end]`，每個事件點各產生一筆 | 同一任務最多出現 3 次，狀態隨時間漂移 |
| V4 起 | `87049ba` 以後 | `snapshot_date = task_start_date`，每個任務唯一一筆 | 歷史數據不再變動，資料不可變 (Immutable) |

### 2.2 Todo / Doing / Done 狀態判斷

| 版本 | 結算點 | Todo 條件 | Doing 條件 | Done 條件 |
|------|--------|-----------|-----------|---------|
| **V2/V3** 快照版 | 任務事件發生日當天 | `snapshot_date < COALESCE(claim, end, ∞)` | `claim ≤ snapshot AND (end IS NULL OR end > snapshot)` | `end ≤ snapshot` |
| **V4** 開單日結算 | 開單日當天 (daily) | `COALESCE(claim, 1900) ≠ start AND (end IS NULL OR end ≠ start)` | `claim = start AND (end IS NULL OR end ≠ start)` | `end = start` |
| **V4.2** 週結算 | 開單週的週日 | `(claim IS NULL OR claim > 週日) AND (end IS NULL OR end > 週日)` | `claim ≤ 週日 AND (end IS NULL OR end > 週日)` | `end ≤ 週日` |
| **V4.2** 月結算 | 開單月的最後一日 | `(claim IS NULL OR claim > 月底) AND (end IS NULL OR end > 月底)` | `claim ≤ 月底 AND (end IS NULL OR end > 月底)` | `end ≤ 月底` |

> 週日 = `toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY`（ISO 週，以週一為首）

### 2.3 Cube.js 週期查詢窗口 (BETWEEN)

| 版本 | 日 block | 週 block (當週) | 月 block |
|------|---------|--------------|---------|
| **V2/V3** | `BETWEEN anchor-6 AND anchor` | `BETWEEN 週一 AND anchor`（截至今天） | `BETWEEN 月初 AND anchor`（截至今天） |
| **V4 Cohort** | 同上，但資料已固定在開單日 | 同上窗口，底層用開單日當天狀態 | 同上窗口 |
| **V4.2 起（現行）** | `BETWEEN anchor-6 AND anchor` | `BETWEEN 週一 AND (週一+6)` **完整週**；當前週取至 anchor | `BETWEEN 月初 AND 月底` **完整月** |

### 2.3b Gold 輸出層演進

| 版本 | Gold 輸出格式 | Cube 讀取方式 | 查詢效能 |
|------|--------------|--------------|---------|
| V2 / V3 / V4~V4.3 | Bitmap 欄位（`groupBitmapState`） | `groupBitmapMerge()` 即時解碼 | ~750ms |
| **V4 Pre-aggregation（現行）** | 整數欄位（`UInt32`） | `sum()` | ~184ms（-75%） |

### 2.4 Acc Rate 分子 / 分母

| 版本 | acc 展開邏輯 | 日 accRate 分母 | 週 accRate 分母 | 月 accRate 分母 | 週末爆表 |
|------|------------|----------------|----------------|----------------|---------|
| **V2** | `range(start, min(end, start+7, end_ts+1))`，`uniqExact` | `total_task`（當日 count） | 週內各日加總 | 月內各日加總 | ❌ |
| **V3** | 同 V2，改 `groupBitmapState` | `total_task` bitmap（當日） | 週內各日 bitmapMerge | 月內各日 bitmapMerge | ❌ |
| **V4 Cohort** | `arrayDistinct(range(start, min(end, start+7)))` + WHERE 過濾在途 | `total_task` bitmap（開單日） | bitmapMerge（開單日落週內） | bitmapMerge（開單日落月內） | ❌ |
| **V4.2** | 同 V4 Cohort | `total_task` bitmap（當日）| **週末截面 total** (todo_w+doing_w+done_w) | **月底截面 total** (todo_m+doing_m+done_m) | ❌ 日維度 |
| **V4.3 現行** | `range(start, start+7)` 固定 7 天，不截斷<br>+ `groupBitmapStateIf` 在途篩選 | **`acc_total_task`（7日滾動總量）** | `(todo+doing)_weekly / total_task` | `(todo+doing)_monthly / total_task` | ✅ |

### 2.5 一例貫通

**範例任務**：開單 2025-12-01 (Mon)，領取 2025-12-04 (Thu)，結案 2025-12-05 (Fri)

| 版本 | 日維度顯示 | 週維度顯示 | 月維度顯示 |
|------|----------|---------|---------|
| **V2/V3** | 12/01=Todo, 12/04=Doing, 12/05=Done（每天不同） | 週報顯示查詢當下的狀態，數字隨 anchor 浮動 | 同理，月報浮動 |
| **V4 Cohort** | 永久 = **Todo**（因 claim≠start_date） | 同樣為 Todo（開單日結算） | Todo |
| **V4.2 / V4.3** | **Todo**（開單日截面） | **Done**（週末 12/07：end=12/05 ≤ 週日） | **Done**（月底 12/31：end=12/05 ≤ 月底） |

---

## 3. 各版本詳細說明

### 3.1 V2 原版 (2026-04-02)

**提交**：`7c4bf44`  
**核心架構**：快照展開（事件日驅動）+ `uniqExact` 精確去重

**ETL 邏輯**
```sql
-- backfill_gold_milestone.sql
ARRAY JOIN [task_start_date, task_claim_date, task_end_date] AS snapshot_date

countIf(snapshot_date < COALESCE(task_claim_date, task_end_date, today()+1)) AS todo_count
countIf(claim IS NOT NULL AND snapshot >= claim AND (end IS NULL OR end > snapshot)) AS doing_count
countIf(end IS NOT NULL AND snapshot >= end) AS done_count

-- backfill_gold_acc.sql
uniqExact(task_id) AS acc_todo_doing
range(start, min(COALESCE(end, today()+2), start+7, end_ts+1))
WHERE end IS NULL OR end > active_date
```

**Cube.js accRate**
```js
accRate = accQty / total_task  // 所有粒度統一，分母為當日/週/月開單量
```

**已知問題**
- 同一任務在 3 個日期各產生一筆，週/月加總有重複計數
- 週末 total_task 趨近 0，accRate 可達數百 %

---

### 3.2 V3 Bitmap 架構 (2026-04-21)

**提交**：`21e6259`  
**核心改動**：`uniqExact` → `groupBitmapState(cityHash64(task_id))`，解決跨維度重複計數

**ETL 邏輯**
```sql
-- snapshot 展開方式不變（仍為事件日 ARRAY JOIN）
groupBitmapStateIf(cityHash64(task_id), snapshot < COALESCE(claim, end, ∞)) AS todo_bm
groupBitmapStateIf(cityHash64(task_id), claim ≤ snapshot AND ...) AS doing_bm
groupBitmapStateIf(cityHash64(task_id), end ≤ snapshot) AS done_bm
groupBitmapState(cityHash64(task_id)) AS acc_bm   -- 在途截斷展開
```

**Cube.js accRate**
```js
accRate = bitmapCardinality(acc_bm) / bitmapCardinality(total_task_bm)
// 分母仍為各粒度快照的 bitmapMerge，週末爆表問題未解
```

---

### 3.3 V4 Cohort 邏輯 (2026-04-28)

**提交**：`87049ba`  
**核心改動**：快照日從「事件日」改為「開單日唯一快照」，狀態永久固定

**ETL 邏輯**
```sql
-- snapshot_date = task_start_date（每任務只有一筆）
groupBitmapStateIf(..., COALESCE(claim, '1900') != start AND (end IS NULL OR end != start)) AS todo
groupBitmapStateIf(..., claim = start AND (end IS NULL OR end != start))                   AS doing
groupBitmapStateIf(..., end = start)                                                        AS done

-- acc 展開改用 arrayDistinct
ARRAY JOIN arrayDistinct(range(start, min(COALESCE(end, today()+1), start+7))) AS active_date_raw
WHERE end IS NULL OR end > toDate(active_date_raw)
```

**語意轉變**：任務狀態從「當天截面動態值」改為「開單日永久分類」，歷史數據不再因任務完工而變動。

---

### 3.4 V4.2 多粒度結算 (2026-04-28)

**提交**：`ac7be83`  
**核心改動**：新增「週末截面」與「月底截面」兩套 Bitmap 欄位，解決週/月維度只能看開單日狀態的問題

**Gold Schema 新增欄位**
```
todo_daily / doing_daily / done_daily       ← 結算點：開單日
todo_weekly / doing_weekly / done_weekly    ← 結算點：開單週的週日
todo_monthly / doing_monthly / done_monthly ← 結算點：開單月的最後一日
```

**週結算條件核心邏輯**
```sql
-- 週日 = toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY
groupBitmapStateIf(..., (claim IS NULL OR claim > 週日) AND (end IS NULL OR end > 週日)) AS todo_weekly
groupBitmapStateIf(..., claim IS NOT NULL AND claim <= 週日 AND (end IS NULL OR end > 週日)) AS doing_weekly
groupBitmapStateIf(..., end <= 週日) AS done_weekly
```

**Cube.js 更新**：日/週/月 SELECT 分別讀取對應欄位集合。

---

### 3.5 V4.3 分母優化 (2026-05-07)

**提交**：`46d3315`  
**核心改動**：修正日維度 accRate 分母邏輯，並實作維度感知公式

**問題根因**
> V4 Cohort 前，accRate 分母為「當日開單量」（1~30 筆），但 acc 分子為「7日累積積壓量」（可達數千筆），時間窗口不對齊，週日分母極小時比率飆升至 300%~500%。

**ETL 改動**
```sql
-- backfill_gold_acc.sql
-- 固定展開 7 天（不再被 task_end_date 截短）
ARRAY JOIN range(task_start_date, task_start_date + 7) AS active_date_raw

-- 同時計算兩個 bitmap：在途 vs 全部
groupBitmapStateIf(cityHash64(task_id),
    task_end_date IS NULL OR task_end_date > toDate(active_date_raw)) AS acc,
groupBitmapState(cityHash64(task_id))                                 AS acc_total_task  -- 新增
```

**Cube.js 維度感知公式**
```js
accTotalQty: { sql: `bitmapCardinality(groupBitmapMergeState(acc_total_task))` },

accRate: {
    sql: `
    CASE
        WHEN any(granularity) = 'Day'
            THEN round(${accQty} * 100.0 / nullIf(${accTotalQty}, 0), 2)
        ELSE
            round((${todoQty} + ${doingQty}) * 100.0 / nullIf(${totalQty}, 0), 2)
    END`
}
// 日 → 7日滾動積壓率；週/月 → 週期落後率
```

**數據效果**（2025-12 月份驗證）

| 指標 | 舊邏輯範圍 | 新邏輯範圍 |
|------|-----------|-----------|
| 日 accRate（平日） | 87%~135% | 14%~22% |
| 日 accRate（週日） | 305%~508% | 15%~17% |
| 週 accRate | — | 11%~18% |
| 月 accRate | — | 6.3% |

---

## 4. 異動記錄模板

**每次修改任何計算邏輯後，請複製以下模板至 [§5 異動歷史](#5-異動歷史) 末尾填寫。**

```markdown
---

### [版本號] [簡要標題] (YYYY-MM-DD)

**提交**：`<commit hash>`  
**異動人**：<Git Author>  
**影響範圍**：<!-- 勾選所有受影響的檔案 -->
- [ ] `sql/etl/dml/backfill_gold_milestone.sql`
- [ ] `sql/etl/dml/backfill_gold_acc.sql`
- [ ] `sql/etl/dml/backfill_gold.sql`
- [ ] `sql/etl/schema/06_gold_kpi_task_completion.sql`
- [ ] `cube/model/cubes/cube_l5_task_periodic.js`
- [ ] 其他：___

**問題描述**
> 說明此次修改要解決的問題，或新增的需求。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| （ETL / Cube / Schema） | 舊邏輯 | 新邏輯 |

**數據影響**
> 說明受影響的時間範圍、指標數值的預期變化。

**回填操作**
- [ ] 不需回填
- [ ] 已執行回填，範圍：`YYYY-MM-DD ~ YYYY-MM-DD`

**驗證結果**
> 附上驗證數字或查詢結果截圖連結。
```

---

## 5. 異動歷史

---

### V2.0 Gold Layer 初始版本 (2026-04-02)

**提交**：`7c4bf44`  
**異動人**：ALBEE.LAI  
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_milestone.sql`（新建）
- [x] `sql/etl/dml/backfill_gold_acc.sql`（新建）
- [x] `sql/etl/dml/backfill_gold.sql`（重構）

**問題描述**
> 原始 Gold 層單一 SQL 在大資料量下 OOM，拆分為 milestone（Todo/Doing/Done）與 acc（7日滾動）兩支獨立 DML。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| acc 計算 | 不存在 | `uniqExact`，ARRAY JOIN 事件日，展開至 `min(end, start+7, end_ts+1)` |
| 狀態分類 | 不存在 | 事件日快照展開，3 個事件點各產生一筆 |
| accRate | 不存在 | `acc / total_task`（當日分母） |

**回填操作**：已執行全量回填

---

### V3.0 Bitmap 架構 (2026-04-21)

**提交**：`21e6259`  
**異動人**：ALBEE.LAI  
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_milestone.sql`
- [x] `sql/etl/dml/backfill_gold_acc.sql`
- [x] `sql/etl/schema/06_gold_kpi_task_completion.sql`
- [x] `cube/model/cubes/cube_l5_task_periodic.js`

**問題描述**
> `uniqExact` 無法在 ClickHouse Bitmap 架構下做精確的跨維度去重，週/月報表出現重複計數。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| acc 計算方法 | `uniqExact(task_id)` | `groupBitmapState(cityHash64(task_id))` |
| 欄位名稱 | `acc_todo_doing` | `acc_bm`（加 _bm 後綴） |
| snapshot 展開 | 同 V2 | 同 V2（未變） |
| accRate 公式 | 同 V2 | 同 V2（未變，分母仍為當日 total_task） |

**回填操作**：已執行全量回填

---

### V4.0 Cohort 邏輯遷移 (2026-04-28)

**提交**：`87049ba`  
**異動人**：ALBEE.LAI  
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_milestone.sql`
- [x] `sql/etl/dml/backfill_gold_acc.sql`
- [x] `sql/etl/dml/backfill_silver.sql`
- [x] `cube/model/cubes/cube_l5_task_periodic.js`

**問題描述**
> V3 快照邏輯導致：(1) 狀態隨時間漂移，歷史報表數字不穩定；(2) `1970` 預設日期被誤判為 Done；(3) SYSTEM 指派人未過濾。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| snapshot_date | 事件日 ARRAY JOIN（最多 3 筆） | `task_start_date`（每任務唯一 1 筆） |
| Todo 條件 | `snapshot < COALESCE(claim, end, ∞)` | `COALESCE(claim, '1900') ≠ start AND (end IS NULL OR end ≠ start)` |
| Doing 條件 | `claim ≤ snapshot AND end > snapshot` | `claim = start AND (end IS NULL OR end ≠ start)` |
| Done 條件 | `end ≤ snapshot` | `end = start` |
| acc 展開 | `range(start, min(end, start+7, end_ts+1))` | `arrayDistinct(range(start, min(end, start+7)))` + WHERE 過濾在途 |
| Silver 過濾 | 無 | 過濾 SYSTEM 指派人、`1970` 預設日期轉 NULL |

**回填操作**：已執行全量回填（含 `--reset`）

---

### V4.2 多粒度結算 (2026-04-28)

**提交**：`ac7be83`  
**異動人**：ALBEE.LAI  
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_milestone.sql`
- [x] `sql/etl/dml/backfill_gold.sql`
- [x] `sql/etl/schema/06_gold_kpi_task_completion.sql`
- [x] `cube/model/cubes/cube_l5_task_periodic.js`

**問題描述**
> V4 Cohort 版本的週/月維度只能反映開單日當天狀態，無法呈現「到週末/月底實際完成了多少」的管理需求。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| Gold 欄位 | `todo`, `doing`, `done`（單一組） | 新增 `_daily` / `_weekly` / `_monthly` 三組 |
| 週結算點 | 無（開單日截面） | `toStartOfWeek(task_start_date, 3) + 6 DAYS`（開單週週日） |
| 月結算點 | 無（開單日截面） | `toLastDayOfMonth(task_start_date)`（開單月月底） |
| 週 NULL claim 處理 | `COALESCE` 可能雙重命中 | 改為 `IS NULL / IS NOT NULL` 精確判斷 |
| Cube.js 週 block | `todo_bm` / `doing_bm` / `done_bm` | `todo_weekly` / `doing_weekly` / `done_weekly` |
| Cube.js 月 block | 同上 | `todo_monthly` / `doing_monthly` / `done_monthly` |
| Cube.js 週 BETWEEN 窗口 | `週一 AND anchor_dt`（部分週） | `週一 AND (週一+6)`（完整週）；當前週取至 anchor |

**回填操作**：已執行全量回填

---

### V4.3 日維度 Acc Rate 分母優化 (2026-05-07)

**提交**：`46d3315`  
**異動人**：ALBEE.LAI  
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_acc.sql`
- [x] `sql/etl/dml/backfill_gold.sql`
- [x] `sql/etl/schema/06_gold_kpi_task_completion.sql`
- [x] `cube/model/cubes/cube_l5_task_periodic.js`

**問題描述**
> 日維度 accRate 分母為「當日開單量」（週末可低至個位數），但分子 acc 為「7日滾動積壓量」（可達數千筆），時間窗口錯位導致週日 accRate 飆升至 305%~508%。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| acc ARRAY JOIN 展開 | `range(start, min(COALESCE(end, today()+1), start+7))` 受 end 截斷 | `range(start, start+7)` 固定 7 天展開 |
| acc bitmap 計算 | `groupBitmapState`（全部展開日） | `groupBitmapStateIf(..., end IS NULL OR end > snapshot)` |
| 新增欄位 | 無 | `acc_total_task`：7日內開單的所有任務（不論結案） |
| 日 accRate 分母 | `total_task`（當日開單量） | `acc_total_task`（7日滾動總開單量） |
| 週 accRate 公式 | `acc / total_task` | `(todo_weekly + doing_weekly) / total_task` |
| 月 accRate 公式 | `acc / total_task` | `(todo_monthly + doing_monthly) / total_task` |
| Cube.js 公式切換 | 統一公式 | `CASE WHEN any(granularity) = 'Day' THEN ... ELSE ...` |

**數據影響**

| 指標 | 修改前（2025-12 月份） | 修改後（2025-12 月份） |
|------|---------------------|---------------------|
| 日 accRate 範圍（平日） | 87% ~ 135% | 14% ~ 22% |
| 日 accRate（週日） | 305% ~ 508% | 15% ~ 17% |
| 月 accRate | — | 6.3% |

**回填操作**：已執行全量回填，範圍 `2025-01-01 ~ 2026-05-07`

---

### 3.6 V4 Pre-aggregation 預聚合 (2026-05-27)

**提交**：`8da3d57` 前後  
**核心改動**：捨棄 Cube.js 即時 Bitmap 運算，引入 `gold.rmv_l5_task_summary` 預聚合整數表

**問題根因**
> Cube.js 在查詢時即時執行 `groupBitmapMerge()`，單一指標查詢需 750ms，多條件查詢可達 30~40s，無法支撐前端互動需求。

**架構改動**

新增 `backfill_gold_summary.sql`，讀取 `rmv_l5_task_completion_phys` + `rmv_l5_acc_phys`，解碼 Bitmap 為整數後寫入 `gold.rmv_l5_task_summary`：

```sql
-- Day 粒度
groupBitmapMerge(total_task)     AS total_qty
groupBitmapMerge(todo_daily)     AS todo_qty
groupBitmapMerge(doing_daily)    AS doing_qty
groupBitmapMerge(done_daily)     AS done_qty
groupBitmapMerge(acc)            AS acc_qty
groupBitmapMerge(acc_total_task) AS acc_total_qty

-- Week/Month 粒度 (acc 用 bitmapOr 去重)
bitmapCardinality(bitmapOr(
    groupBitmapMergeState(todo_weekly),
    groupBitmapMergeState(doing_weekly)
)) AS acc_qty
```

**Cube.js 改動**：`groupBitmapMerge()` → `sum()`，查詢降至 ~184ms（-75%）

**版本邊界**：此 SQL 含 `snapshot_date >= '2026-04-01'` 邊界保護，僅處理 V4 範圍。

**回填操作**：已執行，範圍 `2026-04-01 ~ 2026-05-27`

---

### 3.7 V4.4 Rate 指標修正 (2026-06-05)

**提交**：`2080fdb`  
**核心改動**：新增 `todoRate`/`doingRate`；所有達成率從 `round()` 改為 `floor()`

**問題根因**
> BFF `reports.js` 原本以 `Math.round()` 計算 todoRate/doingRate，不符合 Rule 2「無條件捨去」規格；且 Cube 未提供這兩個指標，需後端另行計算（耦合度高）。

**Cube.js 邏輯改動**

| 指標 | 變更前 | 變更後 |
|------|--------|--------|
| todoRate | 不存在（由 BFF Math.round() 計算） | `floor(todoQty*100/total)` |
| doingRate | 不存在（由 BFF Math.round() 計算） | `floor(doingQty*100/total)` |
| doneRate | `round(done*100/total)` | `if(done≥total, 100, floor(done*100/total))` |
| doingDoneRate | `round(dd*100/total)` | `if(dd≥total, 100, floor(dd*100/total))` |
| accRate (Day) | `round(acc*100/accTotal)` | `if(acc≥accTotal, 100, floor(acc*100/accTotal))` |
| accRate (W/M) | `round((todo+doing)*100/total)` | `floor((todo+doing)*100/total)` |

**數據影響**：指標值 ≤ 0.4% 時，`round` 會顯示 0% 但 `floor` 也顯示 0%；0.5%~0.9% 時 `round` 顯示 1% 而 `floor` 顯示 0%（微幅下修）。

**回填操作**：不需回填（公式層改動，ETL 資料不變）

---

### 3.8 V3.1 歷史資料混合管線 (2026-06-10)

**提交**：`608f31c` 前後  
**SQL**：`sql/etl/dml/backfill_gold_summary_historical.sql`  
**核心改動**：為 2025-10~2026-03 歷史資料建立專屬管線，以混合語意解決日/週/月計算不一致問題

**背景**
> V4 管線（`backfill_gold_summary.sql`）含 `>= 2026-04-01` 邊界保護，2026-03-31 以前的資料在 `gold.rmv_l5_task_summary` 中完全空白，前端歷史頁面無法顯示。

**混合架構設計**

V3.1 管線對三種粒度採用不同語意：

| 粒度 | 語意 | snapshot 來源 | acc 計算方式 |
|------|------|--------------|------------|
| **Day** | 事件日 ARRAY JOIN | task_start/claim/end 各展開一筆 | `rmv_l5_acc_phys` 7D Bitmap（JOIN 後讀取） |
| **Week** | Cohort 週末截面 | `task_start_date`（每任務唯一） | `countIf(todo) + countIf(doing)` |
| **Month** | Cohort 月底截面 | `task_start_date`（每任務唯一） | `countIf(todo) + countIf(doing)` |

**Week 跨年處理（關鍵設計）**

2025-12-29~31 在 ISO 曆屬 2026-W01，但商業上屬 2025 年底。加入以下過濾使其不計入任何週 Cohort，避免污染 2026-W01（一月任務）：

```sql
AND toISOYear(task_start_date) = toYear(task_start_date)
-- 效果：Dec 29-31 (toISOYear=2026 ≠ toYear=2025) 被排除
```

**Cube.js 相容性**

V3.1 使用 ISO 週鍵（`concat(toISOYear, '-W', lpad(toISOWeek, 2, '0'))`），與 V4 管線一致，`cube_l5_task_periodic.js` 無需任何橋接函數。

**驗證結果**（WJ2 CNE NBU E5, 2025-12）

| 期別 | total | todo | doing | done | acc | todo+doing+done=total |
|------|-------|------|-------|------|-----|-----------------------|
| Day 2025-12-25 | 192 | 26 | 1 | 165 | 40 | ✅ |
| Day 2025-12-31 | 211 | 9 | 5 | 197 | 97 | ✅ |
| Week 2025-W51 | 502 | 19 | 12 | 471 | 31 | ✅ |
| Week 2025-W52 | 583 | 29 | 17 | 537 | 46 | ✅ |
| Week 2026-W01 | 12 | 5 | 0 | 7 | 5 | ✅ |
| Month 2025-12 | 2294 | 12 | 93 | 2189 | 105 | ✅ |

**回填操作**：已執行全量回填，範圍 `2025-10-01 ~ 2026-03-31`，含 `OPTIMIZE TABLE FINAL`

---

## 4. 異動記錄模板

**每次修改任何計算邏輯後，請複製以下模板至 [§5 異動歷史](#5-異動歷史) 末尾填寫。**

```markdown
---

### [版本號] [簡要標題] (YYYY-MM-DD)

**提交**：`<commit hash>`
**異動人**：<Git Author>
**影響範圍**：
- [ ] `sql/etl/dml/backfill_gold_summary_historical.sql`
- [ ] `sql/etl/dml/backfill_gold_milestone.sql`
- [ ] `sql/etl/dml/backfill_gold_acc.sql`
- [ ] `sql/etl/dml/backfill_gold_summary.sql`
- [ ] `sql/etl/schema/06_gold_kpi_task_completion.sql`
- [ ] `cube/model/cubes/cube_l5_task_periodic.js`
- [ ] 其他：___

**問題描述**
> 說明此次修改要解決的問題，或新增的需求。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| （ETL / Cube / Schema） | 舊邏輯 | 新邏輯 |

**數據影響**
> 說明受影響的時間範圍、指標數值的預期變化。

**回填操作**
- [ ] 不需回填
- [ ] 已執行回填，範圍：`YYYY-MM-DD ~ YYYY-MM-DD`
  - [ ] V3 管線（backfill_gold_summary_historical.sql）
  - [ ] V4 管線（backfill_gold_summary.sql）

**驗證結果**
> 附上驗證數字或查詢結果。
```

---

## 5. 異動歷史

> 以下為歷史異動記錄，最新在最下方。

---

### V2.0 Gold Layer 初始版本 (2026-04-02)

**提交**：`7c4bf44`
**異動人**：ALBEE.LAI
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_milestone.sql`（新建）
- [x] `sql/etl/dml/backfill_gold_acc.sql`（新建）
- [x] `sql/etl/dml/backfill_gold.sql`（重構）

**問題描述**
> 原始 Gold 層單一 SQL 在大資料量下 OOM，拆分為 milestone（Todo/Doing/Done）與 acc（7日滾動）兩支獨立 DML。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| acc 計算 | 不存在 | `uniqExact`，ARRAY JOIN 事件日，展開至 `min(end, start+7, end_ts+1)` |
| 狀態分類 | 不存在 | 事件日快照展開，3 個事件點各產生一筆 |
| accRate | 不存在 | `acc / total_task`（當日分母） |

**回填操作**：已執行全量回填

---

### V3.0 Bitmap 架構 (2026-04-21)

**提交**：`21e6259`
**異動人**：ALBEE.LAI
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_milestone.sql`
- [x] `sql/etl/dml/backfill_gold_acc.sql`
- [x] `sql/etl/schema/06_gold_kpi_task_completion.sql`
- [x] `cube/model/cubes/cube_l5_task_periodic.js`

**問題描述**
> `uniqExact` 無法在 ClickHouse Bitmap 架構下做精確的跨維度去重，週/月報表出現重複計數。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| acc 計算方法 | `uniqExact(task_id)` | `groupBitmapState(cityHash64(task_id))` |
| 欄位名稱 | `acc_todo_doing` | `acc_bm`（加 _bm 後綴） |
| snapshot 展開 | 同 V2 | 同 V2（未變） |
| accRate 公式 | 同 V2 | 同 V2（分母仍為當日 total_task） |

**回填操作**：已執行全量回填

---

### V4.0 Cohort 邏輯遷移 (2026-04-28)

**提交**：`87049ba`
**異動人**：ALBEE.LAI
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_milestone.sql`
- [x] `sql/etl/dml/backfill_gold_acc.sql`
- [x] `sql/etl/dml/backfill_silver.sql`
- [x] `cube/model/cubes/cube_l5_task_periodic.js`

**問題描述**
> V3 快照邏輯導致：(1) 狀態隨時間漂移；(2) `1970` 預設日期誤判為 Done；(3) SYSTEM 指派人未過濾。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| snapshot_date | 事件日 ARRAY JOIN（最多 3 筆） | `task_start_date`（每任務唯一 1 筆） |
| Todo 條件 | `snapshot < COALESCE(claim, end, ∞)` | `COALESCE(claim,'1900') ≠ start AND (end IS NULL OR end ≠ start)` |
| Doing 條件 | `claim ≤ snapshot AND end > snapshot` | `claim = start AND (end IS NULL OR end ≠ start)` |
| Done 條件 | `end ≤ snapshot` | `end = start` |
| acc 展開 | `range(start, min(end, start+7, end_ts+1))` | `arrayDistinct(range(start, min(end, start+7)))` + WHERE 在途過濾 |
| Silver 過濾 | 無 | 過濾 SYSTEM 指派人、`1970` 預設日期轉 NULL |

**回填操作**：已執行全量回填（含 `--reset`）

---

### V4.2 多粒度結算 (2026-04-28)

**提交**：`ac7be83`
**異動人**：ALBEE.LAI
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_milestone.sql`
- [x] `sql/etl/dml/backfill_gold.sql`
- [x] `sql/etl/schema/06_gold_kpi_task_completion.sql`
- [x] `cube/model/cubes/cube_l5_task_periodic.js`

**問題描述**
> V4 Cohort 版本的週/月維度只能反映開單日當天狀態，無法呈現「到週末/月底實際完成了多少」。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| Gold 欄位 | `todo`, `doing`, `done`（單一組） | 新增 `_daily` / `_weekly` / `_monthly` 三組 |
| 週結算點 | 無 | `toStartOfWeek(task_start_date, 3) + 6 DAYS` |
| 月結算點 | 無 | `toLastDayOfMonth(task_start_date)` |
| Cube.js 週 BETWEEN | `週一 AND anchor_dt` | `週一 AND (週一+6)`（完整週） |

**回填操作**：已執行全量回填

---

### V4.3 日維度 Acc Rate 分母優化 (2026-05-07)

**提交**：`46d3315`
**異動人**：ALBEE.LAI
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_acc.sql`
- [x] `sql/etl/dml/backfill_gold.sql`
- [x] `sql/etl/schema/06_gold_kpi_task_completion.sql`
- [x] `cube/model/cubes/cube_l5_task_periodic.js`

**問題描述**
> 日維度 accRate 分母為「當日開單量」（週末可低至個位數），分子為「7日積壓量」，時間窗口錯位導致週日 accRate 飆升至 305%~508%。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| acc 展開 | `range(start, min(COALESCE(end,today()+1), start+7))` | `range(start, start+7)` 固定 7 天 |
| acc 篩選 | 無（展開時即截斷） | `groupBitmapStateIf(..., end IS NULL OR end > snapshot)` |
| 新增欄位 | 無 | `acc_total_task`（7日滾動總量，不論結案） |
| 日 accRate 分母 | `total_task`（當日開單量） | `acc_total_task`（7日滾動總量） |
| 週/月 accRate | `acc / total_task` | `(todo+doing) / total_task` |

**數據影響**

| 指標 | 修改前（2025-12） | 修改後（2025-12） |
|------|----------------|----------------|
| 日 accRate（平日） | 87%~135% | 14%~22% |
| 日 accRate（週日） | 305%~508% | 15%~17% |

**回填操作**：已執行全量回填，範圍 `2025-01-01 ~ 2026-05-07`

---

### V4 Pre-aggregation 預聚合 (2026-05-27)

**提交**：`8da3d57` 前後
**異動人**：ALBEE.LAI
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_summary.sql`（新建）
- [x] `cube/model/cubes/cube_l5_task_periodic.js`

**問題描述**
> Cube.js 即時 `groupBitmapMerge()` 查詢耗時 750ms～40s，無法支撐前端互動。

**邏輯變更說明**

| 項目 | 變更前 | 變更後 |
|------|--------|--------|
| Gold 輸出格式 | Bitmap 欄位 | 整數 UInt32（預聚合） |
| Cube.js 讀取 | `groupBitmapMerge()` | `sum()` |
| 新增輸出表 | 無 | `gold.rmv_l5_task_summary` (ReplacingMergeTree) |
| 查詢效能 | ~750ms | ~184ms（-75%） |

**回填操作**：已執行，範圍 `2026-04-01 ~ 2026-05-27`

---

### V4.4 Rate 指標修正 (2026-06-05)

**提交**：`2080fdb`
**異動人**：ALBEE.LAI
**影響範圍**：
- [x] `cube/model/cubes/cube_l5_task_periodic.js`

**問題描述**
> BFF `reports.js` 以 `Math.round()` 計算 todoRate/doingRate，不符合 Rule 2 無條件捨去規格。

**邏輯變更說明**

| 指標 | 變更前 | 變更後 |
|------|--------|--------|
| todoRate | 不存在（BFF 計算） | `floor(todo*100/total)` |
| doingRate | 不存在（BFF 計算） | `floor(doing*100/total)` |
| doneRate / doingDoneRate / accRate | `round()` | `floor()`（若 ≥ 100 則固定 100） |

**回填操作**：不需回填

---

### V3.1 歷史資料混合管線 (2026-06-10)

**提交**：`608f31c` 前後
**異動人**：ALBEE.LAI
**影響範圍**：
- [x] `sql/etl/dml/backfill_gold_summary_historical.sql`（新建）

**問題描述**
> `gold.rmv_l5_task_summary` 在 2026-03-31 以前完全無資料，前端歷史頁面空白。需補充 2025-10~2026-03 的日/週/月彙總。

**邏輯變更說明**

| 粒度 | 邏輯 | acc 來源 |
|------|------|---------|
| Day | 事件日 ARRAY JOIN（task_start/claim/end） | `rmv_l5_acc_phys` 7D Bitmap |
| Week | Cohort 開單日 + ISO 週末截面；`toISOYear=toYear` 排除 Dec 29-31 | `countIf(todo)+countIf(doing)` |
| Month | Cohort 開單日 + 月底截面 | `countIf(todo)+countIf(doing)` |

**數據影響**：2025-10-01 ~ 2026-03-31 的 Day/Week/Month 資料從無到有

**回填操作**：
- [x] 已執行回填，範圍：`2025-10-01 ~ 2026-03-31`
  - [x] V3 管線（backfill_gold_summary_historical.sql）

**驗證結果**

| 期別 | total | acc | todo+doing+done=total |
|------|-------|-----|-----------------------|
| Day 2025-12-25 | 192 | 40 | ✅ |
| Week 2025-W52 | 583 | 46 | ✅ |
| Week 2026-W01 | 12 | 5 | ✅ |
| Month 2025-12 | 2294 | 105 | ✅ |
