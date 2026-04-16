# DMP Flowable 業務指標與數據定義 (Business Metrics & Data Definitions)

**文件編號**: 03-MTR-001  
**版本**: 5.1  
**最後更新**: 2026-04-16  
**狀態**: 正式發布 (Released)  
**維護者**: AIT / Data Engineering  
**定位**: 本文件為系統的業務語義辭典，記載 L5 任務指標的精確定義、演進歷程、五階維度血緣與查帳對齊基準。ETL 技術執行細節（SQL 邏輯、管線階段）請見 `docs/03_metrics/ETL_Transformation_Pipeline.md`。

---

## 1. 核心指標定義 (Core Metrics Definitions)

L5 報表核心圍繞「任務狀態」與「所在時間區間」進行多維度拆解。

### 1.1 任務狀態與時間顆粒 (Status & Time Granularity)
報表固定展示以下六種項目 (Item)，**不可新增或調整順序**：

| Item 項目 | 說明與計算邏輯 |
| :--- | :--- |
| **Total Task** | 系統累計至今的所有任務總數 (基準分母)。 |
| **Todo** | 快照時間點當下，處於未認領狀態的任務。 |
| **Doing** | 快照時間點當下，已認領但尚未完成的任務。 |
| **Done** | 快照時間點當下，已完成的任務。 |
| **Doing + Done** | 執行率指標分子 (有進度的任務)。 |
| **Todo + Doing (Acc)** | **累積在途量 (Accumulated)**：採 7 天滑動視窗 (Rolling 7D)。計算基準日(D)往前推6天內曾有活動，且截至 D 日尚未完成的任務總數。 |

### 1.2 動態時間欄位解析 (Dynamic Time Columns)
報表提供跨日、跨週、跨月的動態時序追蹤：

| 欄位名稱 (Pattern) | 說明與動態邏輯 |
| :--- | :--- |
| **Month (`MMM`)** | 計算篩選月份（自然月 1 號至月底）內的任務數與比例。 |
| **W44 (`W${x}`)** | **當月最大週次**。若查詢「當前月」，x 為今日所屬週次；若查詢「歷史月」，x 為該月最後一日所屬週次。若該週未結束，僅統計已發生日期。 |
| **W43 (`W${x}-1`)** | 前一完整週 (Mon ~ Sun) 的數據。 |
| **W42 (`W${x}-2`)** | 前兩完整週 (Mon ~ Sun) 的數據。 |
| **Dn-1 ~ Dn-7** | 基準日逐日往前推 7 天。**注意**：此處的比率分母為 *該日的 7 天滑動總量 (Total Task Rolling 7D)*，以解決週末任務量偏低導致比例暴增的失真問題。 |

---

## 2. 演進歷程與重大修正 (Evolution & Revisions)

本節保留了系統指標邏輯與時俱進的重要分水嶺，供後續查帳與邏輯追溯。

### 2.1 邏輯修正與優化分水嶺 (2026-02-04 核心定調)
針對前期數據不一致，確立了以下四大金律：

1.  **Vx 歸屬優先級反轉 (Vx Attribution Priority)**
    *   **變更前**：工單號規則 (315%) 優先，導致跨流程誤判。
    *   **變更後**：**優先判斷 TaskDefinitionKey 前綴** (V1/V2/V3)。僅在 TaskDef 無法判定時，才套用工單號 (moNumber) 輔助歸屬。（*註：曾在 1/21 短暫將工單號權重拉高，後於此版本校正回歸*）
2.  **時點快照狀態 (Point-in-time Status)**
    *   **變更前**：使用任務「目前最新狀態」統計歷史數據，導致昨日的報表今日看會變動。
    *   **變更後改採動態比對**：
        *   Todo：`snapshot_date < CLAIM_TIME_`
        *   Doing：`snapshot_date >= CLAIM_TIME_ AND snapshot_date < END_TIME_`
        *   Done：`snapshot_date >= END_TIME_`
3.  **累積在途量 (Acc) 滾動邏輯**
    *   由「單日 Todo+Doing」改為真實反映工作負擔的 **7 天滑動活動視窗 (Rolling 7-Day Activity)**。
4.  **Triple-OR 篩選邏輯 (V2 Robust Filtering)**
    *   任務過濾條件精確化：`(START_TIME_ OR CLAIM_TIME_ OR END_TIME_) BETWEEN dates`，確保該週期內沾到邊的任務皆不漏傳。

---

## 3. 製造五階與資料血緣 (Data Lineage Mapping)

本節定義了 L5 報表核心維度：**製造五階 (Region → Vx → Plant → Factory → Line)** 的來源與推導邏輯。

### 3.1 維度串接核心理念
*   **來源雙重保障**：以 Flowable 原生變數表 (`ACT_HI_VARINST`) 為主，若缺失則以公用主檔 (`APP_SRV_COMMON.dbo.MDM_*`) 補齊。
*   **實作位置**：`silver.mv_fact_task_vx`。

### 3.2 五階推導邏輯速查

| 階層 | 欄位 | 主要來源 (VARINST 優先) | 備用來源 (MDM 補齊) | 備註 |
| :--- | :--- | :--- | :--- | :--- |
| **1. 區域** | `region` | `varinst_region` | `mdm_region` (透過 factory 串接) | 如 CNE |
| **2. 流程** | `vx_type` | `TaskDefinitionKey` | `moNumber` 前綴 | 分為 V1/V2/V3 |
| **3. 廠區** | `plant` | `varinst_plant` | `mdm_plant` (Business Key 推導) | 如 WJ2 |
| **4. 工廠** | `factory` | `varinst_factory` | `mdm_factory` | 如 NBU |
| **5. 產線** | `line` | `varinst_line` | `mdm_line` | 如 E5 |

*程式碼實現示意:*
```sql
COALESCE(NULLIF(vd.varinst_region, ''), md.mdm_region) AS region
```

---

## 4. 查帳對齊基準 (Field Verification Reference)

當前台 (Superset / Excel) 數據與後台 (ClickHouse) 出現落差時的單一真理核對口徑。

### 4.1 核心核對準則

| 落差現象 | 可能原因 | 處理方式 |
| :--- | :--- | :--- |
| 前台數量偏高 | 排除規則未生效 | 確認 `is_excluded = 0` 過濾是否套用；檢查 `dummy`、`bypass`、`Q_order` 等 `exclude_reason` |
| 歷史數字今日看不一樣 | 使用了「目前最新狀態」而非快照 | 確認查詢的是 `gold.rmv_l5_task_completion` (snapshot-based)，而非直接對 Silver 做即時聚合 |
| 時區偏差 | MSSQL 為 Server Local Time，ClickHouse 預設 UTC | 查詢時加 `toTimeZone(field, 'Asia/Taipei')` 或確認 ETL 中已轉換 |
| Doing 數量異常 | `CLAIM_TIME_` 可能為 Null | Doing 判定：`task_claim_date IS NOT NULL AND snapshot_date >= task_claim_date AND (task_end_date IS NULL OR snapshot_date < task_end_date)` |

### 4.2 Gold 層對帳查詢（Snapshot-based，正式口徑）

> **重要**: Gold 層採用「時點快照」判定狀態。`snapshot_date` 是任務在 Start/Claim/End 三個事件日期上展開的快照，**不等同**於 `silver.mv_fact_task_vx.task_status` 的當前狀態欄位。正式對帳應以 Gold 層為準。

```sql
-- 驗證特定日期下，V3 NBU 各線體的 Todo/Doing/Done 分佈
SELECT
    snapshot_date, vx_type, plant, factory, line,
    total_task, todo_count, doing_count, done_count, acc_todo_doing
FROM gold.rmv_l5_task_completion
WHERE snapshot_date = '2025-12-31'
  AND vx_type = 'V3'
  AND factory = 'NBU'
ORDER BY line;
```

### 4.3 Silver 層輔助查詢（任務清單稽核）

> 此查詢用於稽核特定維度下原始任務清單（非快照），`task_status` 欄位為任務**目前最新狀態**，適合確認資料是否正確寫入 Silver，不適合用於重現歷史報表數字。

```sql
SELECT task_id, task_status, vx_type, plant, factory, line,
       task_start_date, task_claim_date, task_end_date,
       is_excluded, exclude_reason
FROM silver.mv_fact_task_vx FINAL
WHERE is_excluded = 0
  AND vx_type = 'V3' AND factory = 'NBU'
  AND task_start_date >= '2025-12-01'
  AND task_start_date <= '2025-12-31'
ORDER BY task_start_date DESC
```

---

## 5. SQL 實作規格 (Implementation SQL Specs)

本節記錄各核心業務邏輯的**實際生產 SQL**，與 `sql/etl/dml/` 下的模板保持一致。

### 5.1 Vx 版本歸屬判定（`backfill_silver.sql`）

判定邏輯寫於 `silver.mv_fact_task_vx` 的 `vx_type` 欄位，優先序由高至低：

```sql
CASE
    -- 規則 1（最高優先）：特定工單號前綴 → 強制 V1
    WHEN substring(COALESCE(v_pivot.varinst_moNumber, ''), 1, 3)
             IN ('196','199','200','210','212','213')
    THEN 'V1'

    -- 規則 2-4：TASK_DEF_KEY_ 前綴自動判定
    WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
    WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
    WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'

    -- 規則 5：無法判定，取前兩字元或回填 Unknown
    ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
END AS vx_type
```

> **演進說明（2026-04-15 簡化）**：原版本設有「廠區特權規則」（規則 1：DG3 廠 + 工單號；規則 1b：NPE 廠 + 工單號），於 2026-04-15 驗證後確認為冗餘——全域 323,486 筆及 CNS DG3 SMT ST02 線體 5,179 筆資料，100% 已被工單號規則涵蓋，故予以移除。目前「工單號前綴匹配」為第一優先規則。工單號清單：`196`, `199`, `200`, `210`, `212`, `213`。

---

### 5.2 資料排除規則（`backfill_silver.sql`）

以下邏輯寫於 `is_excluded` 與 `exclude_reason` 兩個欄位：

```sql
-- is_excluded 旗標（0 = 有效資料，1 = 排除）
multiIf(
    tb.LONG_ = 1,                                      1,  -- autoComplete bypass (使用者手動跳過)
    t.TASK_DEF_KEY_ LIKE 'E%',                         1,  -- 系統自動節點 (E 開頭)
    t.TASK_DEF_KEY_ LIKE 'C%',                         1,  -- 系統自動節點 (C 開頭)
    COALESCE(v_pivot.varinst_moNumber,'') LIKE 'Q%',   1,  -- 測試/研發工單
    COALESCE(v_pivot.varinst_moNumber,'') LIKE 'R%',   1,  -- 測試/研發工單
    t.NAME_ LIKE '%Notify%',                           1,  -- 通知節點
    t.NAME_ LIKE '%Dummy%',                            1,  -- 佔位節點
    0                                                      -- 有效資料
) AS is_excluded,

-- exclude_reason 原因標記
multiIf(
    tb.LONG_ = 1,                                          'bypass',
    t.TASK_DEF_KEY_ LIKE 'E%',                            'system_node',
    t.TASK_DEF_KEY_ LIKE 'C%',                            'system_node',
    COALESCE(v_pivot.varinst_moNumber,'') LIKE 'Q%',       'Q_order',
    COALESCE(v_pivot.varinst_moNumber,'') LIKE 'R%',       'R_order',
    t.NAME_ LIKE '%Notify%',                              'notify_task',
    t.NAME_ LIKE '%Dummy%',                               'dummy_task',
    ''
) AS exclude_reason
```

> **注意**：`autoComplete` 旗標（`tb.LONG_ = 1`）的補標由 `backfill_exclusion.sql`（Stage 2b）透過 `ALTER TABLE UPDATE` 非同步處理，因為此旗標可能在任務建立後才被使用者設定。

---

### 5.3 快照展開與狀態計算（`backfill_gold_milestone.sql`）

將每個任務依三個事件日期展開為快照列，再於各快照時間點判定狀態：

```sql
-- Step 1: ARRAY JOIN 展開（一列任務 → 最多三列快照）
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayDistinct(arrayFilter(
    d -> d IS NOT NULL,
    [task_start_date, task_claim_date, task_end_date]
)) AS snapshot_date

-- Step 2: 在各 snapshot_date 時間點上判定任務狀態
SELECT
    snapshot_date,
    vx_type, region, plant, factory, line,
    count() AS total_task,

    -- Todo: 快照時間點早於認領或完結日期（尚未被任何人認領）
    countIf(
        snapshot_date < COALESCE(task_claim_date, task_end_date, today() + 1)
    ) AS todo_count,

    -- Doing: 已認領但尚未完結
    countIf(
        task_claim_date IS NOT NULL
        AND snapshot_date >= task_claim_date
        AND (task_end_date IS NULL OR snapshot_date < task_end_date)
    ) AS doing_count,

    -- Done: 已完結
    countIf(
        task_end_date IS NOT NULL AND snapshot_date >= task_end_date
    ) AS done_count

WHERE is_excluded = 0
  AND snapshot_date >= toDate('{start_ts}')
  AND snapshot_date <= toDate('{end_ts}')
GROUP BY snapshot_date, vx_type, region, plant, factory, line
```

---

### 5.4 ACC 七日滾動（`backfill_gold_acc.sql`）

使用 `range()` 展開任務活躍期間（最多 7 天），再以 `uniqExact` 跨日精確去重：

```sql
-- Step 1: 將每個任務展開為「活躍日期序列」（最多 7 天）
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayMap(
    d -> toDate(d),
    range(
        toUInt32(task_start_date),
        toUInt32(least(
            COALESCE(task_end_date, today() + 2),  -- 未完結則延伸至今日後
            task_start_date + 7,                   -- 最多展開 7 天
            toDate('{end_ts}') + 1                 -- 不超過視窗上限
        ))
    )
) AS active_date

-- Step 2: 過濾完結後的日期，再精確去重
WHERE is_excluded = 0
  AND active_date >= toDate('{start_ts}')
  AND active_date <= toDate('{end_ts}')
  AND (task_end_date IS NULL OR task_end_date > active_date)

SELECT
    active_date AS snapshot_date,
    vx_type, region, plant, factory, line,
    uniqExact(task_id) AS acc_todo_doing  -- 7 日滾動在途唯一任務數
GROUP BY active_date, vx_type, region, plant, factory, line
```

> **與 Milestone 的差異**：Milestone 以「事件日期點」展開（最多 3 列），ACC 以「活躍期間」展開（最多 7 列）。兩者分開計算，於 Stage 6 以 FULL OUTER JOIN 合併為最終金層主表。

---

**相關文件**:
- 完整管線執行細節 → `docs/03_metrics/ETL_Transformation_Pipeline.md`
- SQL 原始模板 → `sql/etl/dml/backfill_*.sql`

---

**文件負責人**: AIT / Data Engineering  
**審核狀態**: §5.1 已對照 `backfill_silver.sql`（2026-04-15 VTYPE 簡化版）更新；§5.2~5.4 對照 `backfill_gold_milestone.sql`、`backfill_gold_acc.sql` 驗證完成，程式碼與文件一致。
