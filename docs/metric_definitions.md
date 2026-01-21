# 流程指標業務定義文件 (Metric Definition Document)

**版本：** 1.2  
**更新日期：** 2026-01-21  
**適用範圍：** DMP Flowable 流程分析系統

---

## ⚠️ 重要資料來源限制說明 (2026-01-21 更新)

### ACT_HI_VARINST 使用規則
- **只有 V1 類型的 Process 與 Task** 會將流程與任務變數寫入 `ACT_HI_VARINST`
- 非 V1 流程或任務即使存在，也不會在 ACT_HI_VARINST 中留下變數資料
- 因此凡是依賴 ACT_HI_VARINST 進行分析、補欄位或維度串接的邏輯，**資料母體僅限於 V1 流程/任務**

### 製造五階資料建構規則
**製造五階定義：** Region → Vx → Plant → Factory → Line

**Flowable 資料限制：**
- Flowable 本身僅提供：Plant、Factory/Production Area、Line
- **Region 與 Vx 並不存在於 Flowable 中，必須從其他主檔補齊**

### 製造五階串接來源表規範（MDM 主檔）
製造五階不可僅依賴 Flowable 欄位，必須從以下主檔表串接補齊：

| 功能層級 | 來源表 |
|----------|--------|
| BU / 組織層 | APP_SRV_COMMON.dbo.MDM_BU_ORG_TYPE_MASTER |
| 製造基地 / Site | APP_SRV_COMMON.dbo.MDM_MFG_SITE_MASTER |
| 廠別 / Plant | APP_SRV_COMMON.dbo.MDM_MFG_PLANT_MASTER |
| 製造區 / Factory Area | APP_SRV_COMMON.dbo.MDM_FACTORY_AREA_MASTER |
| 製造區補充 | APP_SRV_COMMON.dbo.MDM_PROD_AREA_MASTER |
| 產線 / Line | APP_SRV_COMMON.dbo.MDM_LINE_DESC_MASTER |

### Silver 層設計原則
1. 所有依賴 ACT_HI_VARINST 的邏輯，資料來源僅限 V1 流程
2. 製造五階必須來自 Flowable + MDM 表串接，不得只使用 Flowable 欄位
3. Silver 層的核心責任之一：建立「完整製造五階維度結構」
4. Gold KPI 僅能建立在 Silver 已補齊五階與 V1 流程資料之上

### Gold 層指標設計約束
所有與製造維度相關之 KPI（例如：L5 任務完成率）：
- 必須建立於已補齊五階（Region / Vx / Plant / Factory / Line）的 Silver 表
- 且僅限 V1 流程母體

---

## 🔧 V1/V3 歸屬邏輯修正記錄 (2026-01-21)

### 問題背景
在 2026-01-21 的驗證過程中，發現 V1/V3 歸屬邏輯存在錯誤：
- **期望結果**：WJ2+NBU+E5 在 2025-12-28 應該是 V1=3筆, V3=4筆
- **實際結果**：V1=7筆, V3=0筆
- **根本原因**：工單號 315% 規則優先級過高，導致 TaskDefinitionKey 為 V3 的任務被錯誤歸類為 V1

### 修正內容

#### 修正前邏輯（錯誤）
```sql
CASE 
    WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1'
    WHEN t.TaskDefinitionKey LIKE 'V2%' THEN 'V2'
    WHEN t.TaskDefinitionKey LIKE 'V3%' THEN 'V3'
    -- 問題：所有 315% 工單號都歸 V1，優先級過高
    WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%' THEN 'V1'
    WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%|199%|200%|210%|212%|213%' THEN 'V1'
    ELSE COALESCE(substring(t.TaskDefinitionKey, 1, 2), 'Unknown')
END
```

#### 修正後邏輯（正確）
```sql
CASE 
    WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1'
    WHEN t.TaskDefinitionKey LIKE 'V2%' THEN 'V2'
    -- 關鍵修正：只有特定 315% 工單號歸類為 V1
    WHEN COALESCE(v.varinst_moNumber, t.MoNumber) IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
    WHEN t.TaskDefinitionKey LIKE 'V3%' THEN 'V3'
    -- 其他工單號規則保持不變
    WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
         OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
    THEN 'V1'
    ELSE COALESCE(substring(t.TaskDefinitionKey, 1, 2), 'Unknown')
END
```

### 修正影響範圍

#### 數據變化
- **V1 任務數**：從 436,243 筆降至 15,184 筆（減少 421,059 筆錯誤歸類）
- **V3 任務數**：相應增加，恢復正確歸屬
- **驗證結果**：WJ2+NBU+E5 2025-12-28 現在正確顯示 V1=3筆, V3=4筆

#### 修正檔案
- **主要修正**：`scripts/transform_silver_generic_metrics.py`
- **驗證工具**：`scripts/compare_clickhouse_mssql_sync.py`
- **調試工具**：`scripts/debug_mssql_date_logic.py`

### 業務規則澄清

#### 特定 315% 工單號 V1 歸屬規則
只有以下三個特定工單號歸類為 V1：
- `3152600035`
- `3152600036` 
- `3152600037`

其他所有 315% 開頭的工單號（如 `3152600038`, `3152600100` 等）保持原 TaskDefinitionKey 歸屬。

#### 完整 V1 歸屬規則優先級
1. **TaskDefinitionKey 優先**：V1%, V2%, V3% 按原始定義歸屬
2. **特定工單號例外**：上述三個特定 315% 工單號強制歸 V1
3. **其他工單號規則**：196%, 199%, 200%, 210%, 212%, 213% 開頭歸 V1
4. **預設歸屬**：其他情況按 TaskDefinitionKey 前兩字元歸屬

### 技術實現細節

#### 日期邏輯統一
**MSSQL 和 ClickHouse 使用相同的 OR 條件**：
```sql
WHERE (
    CONVERT(DATE, hti.START_TIME_) = '2025-12-28'
    OR CONVERT(DATE, hti.CLAIM_TIME_) = '2025-12-28'
    OR CONVERT(DATE, hti.END_TIME_) = '2025-12-28'
)
```

#### 狀態條件標準化
```sql
-- Done: 任務已完成
SUM(CASE WHEN hti.END_TIME_ IS NOT NULL THEN 1 ELSE 0 END) as done

-- TODO: 任務未指派且未完成
SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NULL THEN 1 ELSE 0 END) as todo

-- DOING: 任務已指派但未完成
SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NOT NULL THEN 1 ELSE 0 END) as doing
```

### 驗證狀態
- ✅ **邏輯修正**：已完成並部署
- ✅ **數據驗證**：期望結果與實際結果一致
- ✅ **MSSQL 一致性**：ClickHouse 與 MSSQL 邏輯統一
- ⚠️ **持續監控**：需要監控 REFRESHABLE MV 是否正確反映修正邏輯

### 後續行動
1. **監控自動化**：確保 Gold 層 REFRESHABLE MV 正確反映修正後的邏輯
2. **測試建立**：建立 V1/V3 歸屬邏輯的自動化測試
3. **文檔更新**：更新相關技術文檔和操作手冊

---

## 維度階層關係

```
FACTORY (工廠)
  └── PLANT (產品線)
        └── LINE_NAME (線別)
```

**說明：**
- 一個 FACTORY 包含多個 PLANT
- 一個 PLANT 包含多個 LINE_NAME
- 流程實例（PROC_INST_ID）在建立時會綁定到特定的 FACTORY / PLANT / LINE_NAME

---

## 指標分類架構

| 分類 | 指標數 | 說明 |
|------|--------|------|
| **存量指標** | 2 | 描述「當下有多少」（快照） |
| **比率指標** | 1 | 描述「佔比關係」 |
| **分布指標** | 1 | 描述「狀態分布」 |
| **維度分析** | 4 | 按不同維度切分的存量 |
| **時長指標** | 2 | 描述「平均耗時」 |
| **健康度指標** | 2 | 描述「流程健康狀況」 |

---

## 指標定義

### 📊 存量指標 (Stock Metrics)

#### 1. 在途業務事件總數

**業務定義：**  
截至查詢時點，尚未完成的業務事件數量。一個業務事件（BUSINESS_KEY）代表一個完整的業務流程實例，可能包含多個子流程和任務。

**業務現象：**  
反映系統中「正在處理中」的業務量，是衡量系統負載的核心指標。

**計數單位：** BUSINESS_KEY（業務事件唯一識別碼）

**主要分析層級：**
- ✅ FACTORY 層級：適合，可安全聚合
- ✅ PLANT 層級：適合，可安全聚合
- ✅ LINE_NAME 層級：適合，可安全聚合

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標，只能取特定時點值）
- **跨維度聚合：** 可加總（SUM）
  - Factory 值 = 該 Factory 下所有 Plant 的加總
  - Plant 值 = 該 Plant 下所有 Line 的加總

**去重邏輯：**
- 按 BUSINESS_KEY 去重（一個業務事件只計算一次）
- 跨 Line 彙總到 Plant 時：`COUNT(DISTINCT BUSINESS_KEY)`
- 跨 Plant 彙總到 Factory 時：`COUNT(DISTINCT BUSINESS_KEY)`

**歷史趨勢分析：**
- 需要每日快照（每天記錄當日的在途數量）
- 趨勢圖顯示：每日在途量變化
- 不可將多日數值相加

**注意事項：**
- ⚠️ 此為時點指標，不同時點的值不可相加
- ⚠️ 必須確保 BUSINESS_KEY 在 FACTORY/PLANT/LINE_NAME 維度上唯一歸屬

---

#### 2. 在途任務總數

**業務定義：**  
截至查詢時點，所有在途業務事件中，狀態為「待辦（TODO）」或「處理中（DOING）」的任務總數。

**業務現象：**  
反映系統中「待處理」和「處理中」的任務量，是衡量人員工作負荷的指標。

**計數單位：** TASK_ID（任務唯一識別碼）

**主要分析層級：**
- ✅ FACTORY 層級：適合，可安全聚合
- ✅ PLANT 層級：適合，可安全聚合
- ✅ LINE_NAME 層級：適合，可安全聚合
- ✅ ASSIGNEE 層級：適合（人員維度）

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 可加總（SUM）
  - Factory 值 = 該 Factory 下所有 Plant 的加總
  - Plant 值 = 該 Plant 下所有 Line 的加總

**去重邏輯：**
- 按 TASK_ID 去重（一個任務只計算一次）
- 跨 Line 彙總到 Plant 時：`COUNT(DISTINCT TASK_ID WHERE TASK_STATUS IN ('TODO', 'DOING'))`
- 跨 Plant 彙總到 Factory 時：`COUNT(DISTINCT TASK_ID WHERE TASK_STATUS IN ('TODO', 'DOING'))`

**歷史趨勢分析：**
- 需要每日快照
- 可分析：每日在途任務量變化、人員負荷趨勢

**注意事項：**
- ⚠️ 此為時點指標，不同時點的值不可相加
- ⚠️ 一個業務事件可能包含多個任務，因此「在途任務數」通常大於「在途業務事件數」

---

### 📈 比率指標 (Ratio Metrics)

#### 3. 事件自動完成率

**業務定義：**  
在所有已完成的任務中，自動完成（DONE_AUTO）的任務佔比。反映流程自動化程度。

**業務現象：**  
衡量流程自動化效率，比率越高代表人工介入越少。

**計算邏輯：**  
```
自動完成率 = DONE_AUTO 任務數 / (DONE + DONE_AUTO) 任務數 × 100%
```

**主要分析層級：**
- ✅ FACTORY 層級：適合
- ✅ PLANT 層級：適合
- ✅ LINE_NAME 層級：適合
- ✅ PROC_DEF_NAME 層級：適合（流程維度）

**聚合原則：**
- **跨時間聚合：** 可加權平均
  - 月平均 = Σ(每日 DONE_AUTO 數) / Σ(每日 DONE + DONE_AUTO 數)
- **跨維度聚合：** 需重新計算，不可直接平均
  - Factory 自動完成率 = Σ(該 Factory 下所有 DONE_AUTO) / Σ(該 Factory 下所有 DONE + DONE_AUTO)
  - ❌ 錯誤：將各 Plant 的自動完成率平均

**去重邏輯：**
- 按 TASK_ID 去重
- 跨 Line 彙總到 Plant 時：
  ```
  SUM(DONE_AUTO 任務數) / SUM(DONE + DONE_AUTO 任務數)
  ```

**歷史趨勢分析：**
- 可按日/週/月計算自動完成率
- 趨勢圖顯示：自動化程度變化

**注意事項：**
- ⚠️ 不可將各維度的比率直接平均，必須用分子分母重新計算
- ⚠️ 只計算已完成任務（DONE + DONE_AUTO），不包含 TODO / DOING / CANCELLED

---

### 📊 分布指標 (Distribution Metrics)

#### 4. TASK_STATUS 分布

**業務定義：**  
所有任務按狀態（TODO / DOING / DONE / DONE_AUTO / CANCELLED）的數量分布。

**業務現象：**  
反映任務生命週期的整體狀態分布，用於健康度檢查。

**計數單位：** TASK_ID

**主要分析層級：**
- ✅ 全局層級：適合（查看整體分布）
- ✅ FACTORY 層級：適合
- ✅ PLANT 層級：適合
- ✅ LINE_NAME 層級：適合

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 可加總（SUM）
  - Factory 各狀態數 = 該 Factory 下所有 Plant 的各狀態數加總

**去重邏輯：**
- 按 TASK_ID 去重
- 跨 Line 彙總到 Plant 時：`COUNT(DISTINCT TASK_ID) GROUP BY TASK_STATUS`

**歷史趨勢分析：**
- 需要每日快照
- 可分析：各狀態佔比變化、異常狀態（CANCELLED）增長趨勢

**注意事項：**
- ⚠️ 此為時點指標，記錄當下的狀態分布
- ⚠️ 各狀態數量加總應等於總任務數

---

### 🔍 維度分析指標 (Dimensional Analysis Metrics)

#### 5. 在途任務數 - 依廠區 (PLANT)

**業務定義：**  
按 PLANT（產品線）維度，統計各 PLANT 的在途任務數（TODO + DOING）。

**業務現象：**  
識別哪些產品線的任務負荷較重，用於資源調配。

**計數單位：** TASK_ID

**主要分析層級：**
- ✅ PLANT 層級：主要分析層級
- ⚠️ FACTORY 層級：需先按 PLANT 分組，再彙總到 FACTORY
- ⚠️ LINE_NAME 層級：可進一步下鑽

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 
  - PLANT → FACTORY：`SUM(各 PLANT 的在途任務數) GROUP BY FACTORY`

**去重邏輯：**
- 按 TASK_ID 去重
- 一個任務只歸屬於一個 PLANT

**歷史趨勢分析：**
- 需要每日快照
- 可分析：各 PLANT 負荷變化、識別瓶頸產品線

**注意事項：**
- ⚠️ 如果 PLANT 為 NULL，需歸類為 'Unknown' 並單獨統計
- ⚠️ 各 PLANT 的在途任務數加總應等於「在途任務總數」

---

#### 6. 在途任務數 - 依部門 (DEPT_NAME)

**業務定義：**  
按部門維度，統計各部門的在途任務數（TODO + DOING）。

**業務現象：**  
識別哪些部門的任務負荷較重，用於人力資源調配。

**計數單位：** TASK_ID

**主要分析層級：**
- ✅ DEPT_NAME 層級：主要分析層級
- ⚠️ 不適合按 FACTORY/PLANT/LINE_NAME 聚合（部門是組織維度，與產線維度正交）

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 
  - 部門維度與產線維度正交，不建議混合聚合

**去重邏輯：**
- 按 TASK_ID 去重
- 一個任務只歸屬於一個部門（由 ASSIGNEE 的部門決定）

**歷史趨勢分析：**
- 需要每日快照
- 可分析：各部門負荷變化、識別人力瓶頸

**注意事項：**
- ⚠️ 部門資訊來自 ASSIGNEE 的所屬部門，如果任務未指派（ASSIGNEE IS NULL），則 DEPT_NAME 為 NULL
- ⚠️ 此指標與 FACTORY/PLANT/LINE_NAME 維度獨立，不建議混合分析

---

#### 7. 在途任務數 - 依人員 (ASSIGNEE)

**業務定義：**  
按人員維度，統計各人員的在途任務數（TODO + DOING）。

**業務現象：**  
識別個人工作負荷，用於任務分配平衡。

**計數單位：** TASK_ID

**主要分析層級：**
- ✅ ASSIGNEE 層級：主要分析層級
- ⚠️ 可彙總到 DEPT_NAME 層級
- ⚠️ 不適合按 FACTORY/PLANT/LINE_NAME 聚合（人員維度與產線維度正交）

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 
  - ASSIGNEE → DEPT_NAME：`SUM(各人員的在途任務數) GROUP BY DEPT_NAME`

**去重邏輯：**
- 按 TASK_ID 去重
- 一個任務只歸屬於一個 ASSIGNEE

**歷史趨勢分析：**
- 需要每日快照
- 可分析：個人負荷變化、識別過載人員

**注意事項：**
- ⚠️ 未指派任務（ASSIGNEE IS NULL）需歸類為 'Unassigned'
- ⚠️ 此指標與 FACTORY/PLANT/LINE_NAME 維度獨立

---

#### 10. 在途流程健康度快照 (Top 10)

**業務定義：**  
按流程定義（PROC_DEF_NAME）維度，統計各流程的在途業務事件數，取前 10 名。

**業務現象：**  
識別哪些流程類型的在途量最多，用於流程優化優先級判斷。

**計數單位：** BUSINESS_KEY

**主要分析層級：**
- ✅ PROC_DEF_NAME 層級：主要分析層級
- ⚠️ 可進一步按 FACTORY/PLANT/LINE_NAME 分組

**聚合原則：**
- **跨時間聚合：** 不可加總（快照指標）
- **跨維度聚合：** 
  - 可按 FACTORY/PLANT/LINE_NAME 分組後，再按 PROC_DEF_NAME 統計

**去重邏輯：**
- 按 BUSINESS_KEY 去重
- 一個業務事件只歸屬於一個流程定義

**歷史趨勢分析：**
- 需要每日快照
- 可分析：各流程在途量變化、識別瓶頸流程

**注意事項：**
- ⚠️ 只取 Top 10，完整分析需移除 LIMIT
- ⚠️ 流程定義維度與產線維度可交叉分析

---

### ⏱️ 時長指標 (Duration Metrics)

#### 8. 平均業務事件總歷時 (秒)

**業務定義：**  
所有已完成業務事件的總歷時（從第一個任務開始到最後一個任務結束）的平均值。

**業務現象：**  
反映業務流程的整體效率，歷時越短代表流程越順暢。

**計算單位：** 秒

**主要分析層級：**
- ✅ FACTORY 層級：適合
- ✅ PLANT 層級：適合
- ✅ LINE_NAME 層級：適合
- ✅ PROC_DEF_NAME 層級：適合（流程維度）

**聚合原則：**
- **跨時間聚合：** 可加權平均
  - 月平均 = Σ(每日總歷時) / Σ(每日完成事件數)
- **跨維度聚合：** 需重新計算，不可直接平均
  - Factory 平均歷時 = Σ(該 Factory 下所有事件總歷時) / Σ(該 Factory 下完成事件數)
  - ❌ 錯誤：將各 Plant 的平均歷時平均

**去重邏輯：**
- 按 BUSINESS_KEY 去重
- 只計算已完成事件（FINAL_END_TIME IS NOT NULL）

**歷史趨勢分析：**
- 可按日/週/月計算平均歷時
- 趨勢圖顯示：流程效率變化

**注意事項：**
- ⚠️ 不可將各維度的平均值直接平均，必須用總歷時/事件數重新計算
- ⚠️ 只計算已完成事件，在途事件不納入

---

#### 9. 平均任務處理時長 (秒)

**業務定義：**  
所有已完成任務（DONE）的處理時長（從 CLAIM_TIME 到 END_TIME）的平均值。

**業務現象：**  
反映人員處理任務的效率，處理時長越短代表效率越高。

**計算單位：** 秒

**主要分析層級：**
- ✅ FACTORY 層級：適合
- ✅ PLANT 層級：適合
- ✅ LINE_NAME 層級：適合
- ✅ ASSIGNEE 層級：適合（人員維度）
- ✅ PROC_DEF_NAME 層級：適合（流程維度）

**聚合原則：**
- **跨時間聚合：** 可加權平均
  - 月平均 = Σ(每日總處理時長) / Σ(每日完成任務數)
- **跨維度聚合：** 需重新計算，不可直接平均
  - Factory 平均處理時長 = Σ(該 Factory 下所有任務處理時長) / Σ(該 Factory 下完成任務數)

**去重邏輯：**
- 按 TASK_ID 去重
- 只計算已完成任務（TASK_STATUS = 'DONE'）

**歷史趨勢分析：**
- 可按日/週/月計算平均處理時長
- 可分析：人員效率變化、流程瓶頸識別

**注意事項：**
- ⚠️ 不可將各維度的平均值直接平均
- ⚠️ 只計算 DONE 狀態，不包含 DONE_AUTO（自動完成無處理時長）

---

### 🏥 健康度指標 (Health Metrics)

#### 11. 依流程的自動完成率 (Top 10)

**業務定義：**  
按流程定義（PROC_DEF_NAME）維度，計算各流程的自動完成率，取前 10 名。

**業務現象：**  
識別哪些流程的自動化程度最高，用於自動化推廣參考。

**計算邏輯：**  
```
流程自動完成率 = 該流程的 DONE_AUTO 任務數 / 該流程的 (DONE + DONE_AUTO) 任務數 × 100%
```

**主要分析層級：**
- ✅ PROC_DEF_NAME 層級：主要分析層級
- ⚠️ 可進一步按 FACTORY/PLANT/LINE_NAME 分組

**聚合原則：**
- **跨時間聚合：** 可加權平均
- **跨維度聚合：** 需重新計算
  - Factory 層級某流程的自動完成率 = Σ(該 Factory 下該流程的 DONE_AUTO) / Σ(該 Factory 下該流程的 DONE + DONE_AUTO)

**去重邏輯：**
- 按 TASK_ID 去重
- 只計算已完成任務（DONE + DONE_AUTO）

**歷史趨勢分析：**
- 可按日/週/月計算各流程自動完成率
- 可分析：自動化推進效果

**注意事項：**
- ⚠️ 只取 Top 10，完整分析需移除 LIMIT
- ⚠️ 需設定最小樣本數（如：完成任務數 >= 10）避免小樣本偏差

---

## 指標聚合矩陣

| 指標 | 跨時間聚合 | 跨 LINE 聚合 | 跨 PLANT 聚合 | 跨 FACTORY 聚合 |
|------|-----------|-------------|--------------|----------------|
| 在途業務事件總數 | ❌ 快照 | ✅ SUM | ✅ SUM | ✅ SUM |
| 在途任務總數 | ❌ 快照 | ✅ SUM | ✅ SUM | ✅ SUM |
| 事件自動完成率 | ✅ 加權平均 | ⚠️ 重新計算 | ⚠️ 重新計算 | ⚠️ 重新計算 |
| TASK_STATUS 分布 | ❌ 快照 | ✅ SUM | ✅ SUM | ✅ SUM |
| 在途任務數-依廠區 | ❌ 快照 | ✅ SUM | ✅ SUM | ✅ SUM |
| 在途任務數-依部門 | ❌ 快照 | N/A | N/A | N/A |
| 在途任務數-依人員 | ❌ 快照 | N/A | N/A | N/A |
| 平均業務事件總歷時 | ✅ 加權平均 | ⚠️ 重新計算 | ⚠️ 重新計算 | ⚠️ 重新計算 |
| 平均任務處理時長 | ✅ 加權平均 | ⚠️ 重新計算 | ⚠️ 重新計算 | ⚠️ 重新計算 |
| 在途流程健康度快照 | ❌ 快照 | ✅ SUM | ✅ SUM | ✅ SUM |
| 依流程的自動完成率 | ✅ 加權平均 | ⚠️ 重新計算 | ⚠️ 重新計算 | ⚠️ 重新計算 |

**圖例：**
- ✅ 可直接聚合
- ⚠️ 需重新計算（不可直接平均或加總）
- ❌ 不可聚合
- N/A 維度不適用

---

## Gold 層 MVIEW 設計建議

### 方案：每日快照表 + 維度預聚合

```sql
CREATE MATERIALIZED VIEW gold.daily_metrics_snapshot
REFRESH EVERY 1 DAY
AS
SELECT
    today() AS snapshot_date,
    FACTORY,
    PLANT,
    LINE_NAME,
    PROC_DEF_NAME,
    
    -- 存量指標（快照）
    COUNT(DISTINCT CASE WHEN FINAL_END_TIME IS NULL THEN BUSINESS_KEY END) AS in_progress_events,
    COUNT(DISTINCT CASE WHEN TASK_STATUS IN ('TODO', 'DOING') THEN TASK_ID END) AS in_progress_tasks,
    
    -- 比率指標（分子分母分開存）
    COUNT(DISTINCT CASE WHEN TASK_STATUS = 'DONE_AUTO' THEN TASK_ID END) AS done_auto_tasks,
    COUNT(DISTINCT CASE WHEN TASK_STATUS IN ('DONE', 'DONE_AUTO') THEN TASK_ID END) AS done_total_tasks,
    
    -- 時長指標（總和 + 計數，用於計算平均）
    SUM(CASE WHEN FINAL_END_TIME IS NOT NULL THEN TOTAL_DURATION_SEC ELSE 0 END) AS total_event_duration_sec,
    COUNT(DISTINCT CASE WHEN FINAL_END_TIME IS NOT NULL THEN BUSINESS_KEY END) AS completed_events,
    
    SUM(CASE WHEN TASK_STATUS = 'DONE' THEN WORK_DURATION_SEC ELSE 0 END) AS total_work_duration_sec,
    COUNT(DISTINCT CASE WHEN TASK_STATUS = 'DONE' THEN TASK_ID END) AS done_tasks
    
FROM silver.RMV_HI_PROC_TASK_NODE
LEFT JOIN silver.RMV_HI_BIZ_EVENT_INFO USING (BUSINESS_KEY)
GROUP BY snapshot_date, FACTORY, PLANT, LINE_NAME, PROC_DEF_NAME
```

**優點：**
- 每日快照，支援歷史趨勢分析
- 分子分母分開存，支援任意維度重新計算比率
- 預聚合到最細粒度，查詢時可靈活彙總

---

## 使用範例

### 查詢 Factory 層級的在途任務數（跨 Plant 聚合）

```sql
SELECT 
    FACTORY,
    SUM(in_progress_tasks) AS total_in_progress_tasks
FROM gold.daily_metrics_snapshot
WHERE snapshot_date = today()
GROUP BY FACTORY
ORDER BY total_in_progress_tasks DESC
```

### 查詢 Factory 層級的自動完成率（重新計算）

```sql
SELECT 
    FACTORY,
    SUM(done_auto_tasks) AS auto_tasks,
    SUM(done_total_tasks) AS total_tasks,
    ROUND(SUM(done_auto_tasks) * 100.0 / SUM(done_total_tasks), 2) AS auto_rate_pct
FROM gold.daily_metrics_snapshot
WHERE snapshot_date = today()
GROUP BY FACTORY
ORDER BY auto_rate_pct DESC
```

### 查詢過去 30 天的在途任務趨勢（Factory 層級）

```sql
SELECT 
    snapshot_date,
    FACTORY,
    SUM(in_progress_tasks) AS total_in_progress_tasks
FROM gold.daily_metrics_snapshot
WHERE snapshot_date >= today() - INTERVAL 30 DAY
GROUP BY snapshot_date, FACTORY
ORDER BY snapshot_date, FACTORY
```

---

## 附錄：常見錯誤與避免方法

### ❌ 錯誤 1：直接平均比率指標

```sql
-- 錯誤：將各 Plant 的自動完成率平均
SELECT AVG(auto_rate_pct) FROM plant_metrics
```

**正確做法：**
```sql
-- 正確：用分子分母重新計算
SELECT SUM(done_auto_tasks) * 100.0 / SUM(done_total_tasks) AS auto_rate_pct
FROM plant_metrics
```

---

### ❌ 錯誤 2：跨時間加總快照指標

```sql
-- 錯誤：將每日在途任務數相加
SELECT SUM(in_progress_tasks) FROM daily_snapshot
WHERE snapshot_date BETWEEN '2026-01-01' AND '2026-01-31'
```

**正確做法：**
```sql
-- 正確：顯示每日趨勢，不相加
SELECT snapshot_date, in_progress_tasks FROM daily_snapshot
WHERE snapshot_date BETWEEN '2026-01-01' AND '2026-01-31'
ORDER BY snapshot_date
```

---

### ❌ 錯誤 3：忽略 NULL 值導致重複計算

```sql
-- 錯誤：未處理 PLANT IS NULL 的情況
SELECT PLANT, COUNT(*) FROM tasks GROUP BY PLANT
```

**正確做法：**
```sql
-- 正確：將 NULL 歸類為 'Unknown'
SELECT COALESCE(PLANT, 'Unknown') AS PLANT, COUNT(*) FROM tasks GROUP BY PLANT
```

---

**文件結束**


---

## 通用指標定義

### 📊 L5 任務執行完成率 (L5 Task Completion Rate)

**業務定義：**  
依據 Vx（V1~V9）流程類型，統計各時間區間內任務的完成狀態分布與完成率。

---

#### 欄位定義

##### 篩選條件列

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| Vx | Text | 依據「Vx」此一篩選條件，動態顯示對應結果 |
| Plant | Text | 依據「Plant」此一篩選條件，動態顯示對應結果 |
| Factory | Text | 依據「Factory」此一篩選條件，動態顯示對應結果 |
| Line | Text | 依據「Line」此一篩選條件，動態顯示對應結果 |

##### 指標列（第一層表頭）

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| Item | Text | 任務狀態項目（共六項固定值，不包含次指標列 Task Status） |
| Total | Text | 固定值為 Total |
| Month (MMM) | 日期（動態） | 依篩選條件「Month」顯示對應值，格式為英文月份縮寫（Jan、Feb、Mar…） |
| W${x} | Text（動態） | 查詢月份為當前月：x = 當前日期所屬週次；查詢月份為歷史月份：x = 該月最後一天所屬週次 |
| W(${x}-1) | Text（動態） | 顯示前一週 |
| W(${x}-2) | Text（動態） | 顯示前兩週 |
| Dn-1 (MM/DD) | 日期（動態） | 當月：顯示今日 -1；歷史月份：顯示該月最後一天 |
| Dn-2 ～ Dn-7 (MM/DD) | 日期（動態） | 顯示當天 -2 ～ -7 的日期 |

##### 次指標列（第二層表頭）

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| Task Status | 固定值 | 每個時間區間下，拆分為 Task Qty 與 (%) |

---

#### 週次計算邏輯

| 情境 | 說明 |
|------|------|
| 查詢月份 = 2025-11，當前日期 = 2025/11/03 | x = 45 |
| 查詢月份 = 2025-10 | x = 44（2025/10/31 所屬週次） |
| 查詢月份 = 2025-09 | x = 40（2025/09/30 所屬週次） |
| W40 範圍 | 2025/09/29（一）～2025/10/05（日） |
| 查詢 2025-09 | W40 計算區間為 9/29 ～ 10/5 |
| 當前日期 = 2025/11/01，查詢月份 = 2025-11 | x = 44，計算區間為 2025/10/27（一）～2025/11/01（六） |

---

#### 週次計算公式

```
週次 (ISO Week) = toISOWeek(date)
```

- 使用 ISO 8601 週次標準
- 週一為每週第一天
- 第一週為包含該年第一個星期四的週

---

#### 時間區間說明

| 區間類型 | 說明 |
|---------|------|
| Total | 該月份所有資料的彙總 |
| Month (MMM) | 該月份的彙總（與 Total 相同） |
| W${x} | 當前週或該月最後一天所屬週 |
| W(${x}-1) | 前一週 |
| W(${x}-2) | 前兩週 |
| Dn-1 ~ Dn-7 | 最近 7 天的每日資料 |

---

#### 任務狀態項目（Item）詳細定義

##### 1. Total Task

| 指標 | 計算規則 |
|------|---------|
| Task Qty | `task_status = 'todo'` + `task_status = 'Doing'` + `task_status = 'Done'`，且 `task_bypass = 'N'` 的任務數加總 |
| (%) | 無任何公式，僅顯示「-」 |

---

##### 2. Todo

| 指標 | 計算規則 |
|------|---------|
| Task Qty | `task_status = 'todo'` 且 `task_bypass = 'N'` 的任務數加總，需排除 L5 任務編號以「E」、「C」開頭的任務 |
| (%) | Todo 的值 / Total Task 的值 |

**任務歸屬規則（依 Log 檔案）：**
- L5 任務編號開頭為「V1」→ 計算於 V1 任務
- L5 任務編號開頭為「V2」→ 計算於 V2 任務
- L5 任務編號開頭為「V3」→ 計算於 V3 任務

**V1 調用 V3 流程之任務歸屬規則：**
- 工單編號以 196 / 199 / 200 / 210 / 212 / 213 / 315 開頭者
- 不論 L5 任務節點為 V1 或 V3，皆算在 V1 任務數

**11/24 更新（12 月第二次迭代）：**
- 需排除 Q 工單、R 工單
- 當工單依規則歸屬於 V1 時：
  - 製造產品廠包含「NPE」→ V1 NPE 任務數
  - 不包含「NPE」→ V1 MFG 任務數
  - All = V1 NPE + V1 MFG

---

##### 3. Doing

| 指標 | 計算規則 |
|------|---------|
| Task Qty | `task_status = 'Doing'` 且 `task_bypass = 'N'` 的任務數加總，需排除 L5 任務編號以「E」、「C」開頭的任務 |
| (%) | Doing 的值 / Total Task 的值 |

**任務歸屬規則（依 Log 檔案）：**
- L5 任務編號開頭為「V1」→ 計算於 V1 任務
- L5 任務編號開頭為「V2」→ 計算於 V2 任務
- L5 任務編號開頭為「V3」→ 計算於 V3 任務

**V1 調用 V3 流程之任務歸屬規則：**
- 工單編號以 196 / 199 / 200 / 210 / 212 / 213 / 315 開頭者
- 不論 L5 任務節點為 V1 或 V3，皆算在 V1 任務數

**11/24 更新：**
- 需排除 Q 工單、R 工單
- 當工單依規則歸屬於 V1 時：
  - 製造產品廠包含「NPE」→ V1 NPE 任務數
  - 不包含「NPE」→ V1 MFG 任務數
  - All = V1 NPE + V1 MFG

---

##### 4. Done

| 指標 | 計算規則 |
|------|---------|
| Task Qty | `task_status = 'Done'` 且 `task_bypass = 'N'` 的任務數加總，需排除 L5 任務編號以「E」、「C」開頭的任務 |
| (%) | Done 的值 / Total Task 的值 |

**任務歸屬規則（依 Log 檔案）：**
- L5 任務編號開頭為「V1」→ 計算於 V1 任務
- L5 任務編號開頭為「V2」→ 計算於 V2 任務
- L5 任務編號開頭為「V3」→ 計算於 V3 任務

**V1 調用 V3 流程之任務歸屬規則：**
- 工單編號以 196 / 199 / 200 / 210 / 212 / 213 / 315 開頭者
- 不論 L5 任務節點為 V1 或 V3，皆算在 V1 任務數

**11/24 更新：**
- 需排除 Q 工單、R 工單
- 當工單依規則歸屬於 V1 時：
  - 製造產品廠包含「NPE」→ V1 NPE 任務數
  - 不包含「NPE」→ V1 MFG 任務數
  - All = V1 NPE + V1 MFG

---

##### 5. Doing + Done

| 指標 | 計算規則 |
|------|---------|
| Task Qty | Doing 任務數 + Done 任務數 |
| (%) | (Doing + Done) / Total Task |

---

##### 6. Todo + Doing (Acc)

累計在途任務數，依不同時間區間計算：

| 時間區間 | 計算規則 |
|---------|---------|
| Total | 計算最新時間至最早時間的所有 Todo + Doing 任務數 |
| (Oct) N Month | 計算該月第一日至該月最後一日（查詢月份為當月時，最後一日即為當日）的所有 Todo + Doing 任務數；跨月後數值需固定，不允許再更動 |
| W44 (Wx) | 計算當週第一日（週一）至最後一日（週日）的所有 Todo + Doing 任務數 |
| W43 (Wx-1) | 計算 Wx-1 週第一日（週一）至最後一日（週日）的所有 Todo + Doing 任務數；跨週後數值需固定，不允許再更動 |
| W42 (Wx-2) | 計算 Wx-2 週第一日（週一）至最後一日（週日）的所有 Todo + Doing 任務數；跨週後數值需固定，不允許再更動 |
| 10/29 (D1) | 計算 10/23 ～ 10/29（當日至前六日）所有 Todo + Doing 任務數；跨日後數值需固定 |
| 10/28 (D2) | 計算 10/22 ～ 10/28（當日至前六日）所有 Todo + Doing 任務數；跨日後數值需固定 |
| 10/27 (D3) | 計算 10/21 ～ 10/27（當日至前六日）所有 Todo + Doing 任務數；跨日後數值需固定 |
| 10/26 (D4) | 計算 10/20 ～ 10/26（當日至前六日）所有 Todo + Doing 任務數；跨日後數值需固定 |
| 10/25 (D5) | 計算 10/19 ～ 10/25（當日至前六日）所有 Todo + Doing 任務數；跨日後數值需固定 |
| 10/24 (D6) | 計算 10/18 ～ 10/24（當日至前六日）所有 Todo + Doing 任務數；跨日後數值需固定 |
| 10/23 (D7) | 計算 10/17 ～ 10/23（當日至前六日）所有 Todo + Doing 任務數；跨日後數值需固定 |

---

#### 資料來源確認

| 欄位 | 來源表 | 來源欄位 | 取得方式 |
|------|--------|---------|---------|
| 工單編號判斷（196/199/200/210/212/213/315） | `APP_SRV_BPM.dbo.ACT_HI_VARINST` | `TEXT_` (NAME_='moNumber') | 轉置後取得 moNumber，判斷是否以 196/199/200/210/212/213/315 **開頭** |
| NPE 判斷 | `APP_SRV_BPM.dbo.ACT_HI_PROCINST` | `BUSINESS_KEY_` | `BUSINESS_KEY_ LIKE '%NPE%'` 或 `BUSINESS_KEY_ NOT LIKE '%NPE%'` |
| Q 工單判斷 | `APP_SRV_BPM.dbo.ACT_HI_VARINST` | `TEXT_` (NAME_='moNumber') | 轉置後取得 moNumber，判斷 `moNumber LIKE 'Q%'` |
| R 工單判斷 | `APP_SRV_BPM.dbo.ACT_HI_VARINST` | `TEXT_` (NAME_='moNumber') | 轉置後取得 moNumber，判斷 `moNumber LIKE 'R%'` |
| V1/V2/V3 歸屬 | `APP_SRV_BPM.dbo.ACT_HI_TASKINST` | `TASK_DEF_KEY_` | 欄位前兩個字元（V1/V2/V3） |

---

#### ⚠️ 資料來源變更說明 (2026-01-16)

**變更內容：** 工單編號判斷從 `ACT_HI_PROCINST.NAME_` 改為 `ACT_HI_VARINST.moNumber`

**變更原因：**

1. **欄位內容不同**：
   - `ACT_HI_PROCINST.NAME_` 是流程名稱（如 `V32025111700005`）
   - `ACT_HI_VARINST.moNumber` 是實際工單編號（如 `199170900339`）

2. **分析結果**：
   | 判斷方式 | 符合 V1 的流程數 |
   |---------|-----------------|
   | 兩者都判斷為 V1 | 988 |
   | 只有 `NAME_` 判斷為 V1 | 1,890 |
   | 只有 `moNumber` 判斷為 V1 | **5,368** |

3. **結論**：使用 `varinst.moNumber` 可以找到更多符合 V1 特殊規則的任務，更符合業務需求。

**ACT_HI_VARINST 表說明：**
- 這是一個 EAV (Entity-Attribute-Value) 結構的表
- `PROC_INST_ID_`: 流程實例 ID（Entity）
- `NAME_`: 變數名稱（Attribute）
- `TEXT_`: 變數值（Value）
- 需要轉置（Pivot）才能取得 moNumber 欄位

**轉置 SQL 範例：**
```sql
SELECT 
    PROC_INST_ID_,
    MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
FROM ACT_HI_VARINST
WHERE NAME_ = 'moNumber'
GROUP BY PROC_INST_ID_
```

---

#### 資料來源 SQL 範例

**V1 MFG 判斷（工單編號開頭為 196/199/200/210/212/213/315 且製造產品廠不包含 NPE）：**
```sql
-- 使用 varinst.moNumber 判斷工單編號（開頭判斷）
WITH varinst_pivoted AS (
    SELECT 
        PROC_INST_ID_,
        MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
    WHERE NAME_ = 'moNumber'
    GROUP BY PROC_INST_ID_
)
SELECT p.* 
FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST p
INNER JOIN varinst_pivoted v ON p.PROC_INST_ID_ = v.PROC_INST_ID_
WHERE (v.moNumber LIKE '196%' OR v.moNumber LIKE '199%' OR v.moNumber LIKE '200%' 
       OR v.moNumber LIKE '210%' OR v.moNumber LIKE '212%' OR v.moNumber LIKE '213%'
       OR v.moNumber LIKE '315%')
  AND p.BUSINESS_KEY_ NOT LIKE '%NPE%'
```

**V1 NPE 判斷（工單編號開頭為 196/199/200/210/212/213/315 且製造產品廠包含 NPE）：**
```sql
-- 使用 varinst.moNumber 判斷工單編號（開頭判斷）
WITH varinst_pivoted AS (
    SELECT 
        PROC_INST_ID_,
        MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
    WHERE NAME_ = 'moNumber'
    GROUP BY PROC_INST_ID_
)
SELECT p.* 
FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST p
INNER JOIN varinst_pivoted v ON p.PROC_INST_ID_ = v.PROC_INST_ID_
WHERE (v.moNumber LIKE '196%' OR v.moNumber LIKE '199%' OR v.moNumber LIKE '200%' 
       OR v.moNumber LIKE '210%' OR v.moNumber LIKE '212%' OR v.moNumber LIKE '213%'
       OR v.moNumber LIKE '315%')
  AND p.BUSINESS_KEY_ LIKE '%NPE%'
```

**排除 Q 工單：**
```sql
-- 使用 varinst.moNumber 判斷
WITH varinst_pivoted AS (
    SELECT 
        PROC_INST_ID_,
        MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
    WHERE NAME_ = 'moNumber'
    GROUP BY PROC_INST_ID_
)
SELECT * FROM varinst_pivoted WHERE moNumber LIKE 'Q%'
```

**排除 R 工單：**
```sql
-- 使用 varinst.moNumber 判斷
WITH varinst_pivoted AS (
    SELECT 
        PROC_INST_ID_,
        MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
    WHERE NAME_ = 'moNumber'
    GROUP BY PROC_INST_ID_
)
SELECT * FROM varinst_pivoted WHERE moNumber LIKE 'R%'
```

---

#### 待補充

- [ ] L5 任務編號對應的欄位名稱（TASK_DEF_KEY_ 確認）
- [ ] 製造產品廠對應的欄位名稱（factory 欄位來源確認）


---

### 📊 人員使用率 (User Utilization)

**業務定義：**  
在指定 Vx / Plant / Factory / Line 與時間區間下，實際有使用紀錄的人員數（Active Users）÷ 具備對應系統使用權限的人員數（Config Users）。

---

#### 欄位定義

##### 篩選條件列

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| Vx | Text | 依據「Vx」篩選條件，動態顯示對應結果 |
| Plant | Text | 依據「Plant」篩選條件，動態顯示對應結果 |
| Factory | Text | 依據「Factory」篩選條件，動態顯示對應結果 |
| Line | Text | 依據「Line」篩選條件，動態顯示對應結果 |

##### 指標列（第一層表頭 / 時間維度）

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| Item | Text | 人員使用率相關指標項目（固定三項） |
| Total | Numeric + % | 累計至今的人員使用率指標 |
| (Oct) N Month | Numeric + % | 依篩選月份顯示；ALL 時自動抓取當月 |
| W44（W(x)） | Numeric + % | 當週（週一～週日） |
| W43（W(x-1)） | Numeric + % | 上一週（週一～週日） |
| W42（W(x-2)） | Numeric + % | 上上週（週一～週日） |
| D1–D7 | Numeric + % | 當日起往前 7 天（D1 = 當日） |

##### 表身區指標項目

| Item | 類型 | 說明 |
|------|------|------|
| Active Users | 整數 | 實際有使用紀錄的人員數 |
| Config Users | 整數 | 具備對應系統使用權限的人員數 |
| Active Users / Config Users | 百分比 | 人員使用率 |

---

#### Active Users 計算邏輯

**資料來源：** Log 檔（`bronze.common_flowable_task_stats`）

**篩選條件：**
- `TaskDefinitionKey` 包含對應 V1/V2/V3 任務字眼
- `TaskStatus = 'Done'` 或 `'Doing'`
- 統計 `TaskAssigneeName` 去重人數

**額外條件：**
- 使用者必須同時存在於對應 Vx 成員列表（Config Users）中
- 不在 Config Users 名單中的人員不計算

**範例：**
```
員工 A, B, C, D 均有 V1 任務使用紀錄
但員工 C 不在 V1 成員列表中
→ V1 Active Users = A, B, D（排除 C）
```

---

#### Config Users 計算邏輯

##### V1 計算規則

**UserGroupName 白名單（符合其中一個即可）：**

| ID | UserGroupName | 說明 |
|----|---------------|------|
| 1 | User | 普通用戶 |
| 2 | PMUser | V1 |
| 3 | PowerUser | 班組長 |

**UserGroupName 排除名單（有任一個就排除）：**

| ID | UserGroupName | 說明 |
|----|---------------|------|
| 4 | ManagerUser | 產品廠長 |
| 5 | LocalAdmin | PIT |
| 6 | GlobalAdmin | Vx |
| 7 | SystemAdmin | IT |
| 8 | InternalAudit | 內部稽核 |
| 9 | SeniorOfficers&DTO | 高階長官 & DTO |

**判斷邏輯：**
```
排除規則優先於白名單

IF 使用者有任一排除身分（4~9）
    THEN → 排除，不計算
ELSE IF 使用者有任一白名單身分（1~3）
    THEN → 納入 V1 Config Users
ELSE
    → 不納入
```

**範例：**
- 使用者有 User(1) + GlobalAdmin(6) → **排除**（有排除身分）
- 使用者只有 User(1) → **納入**
- 使用者有 PMUser(2) + PowerUser(3) → **納入**

**資料來源：** `APP_SRV_COMMON.dbo.UserGroup` → `bronze.common_user_group`

##### V2 & V3 計算規則

**UserGroupName 條件：**
- 必須完全符合 `UserGroupName = 'User'`
- 如果有包含其他身分，需排除

---

#### NodeCodes + MFG_PLANT_CODES 歸屬規則

| NodeCodes | MFG_PLANT_CODES | 歸屬 |
|-----------|-----------------|------|
| V1.x | * | V1 成員 |
| V1.x | LIKE 'NPE' | V1 成員 |
| V2.x | * | V2 成員 |
| V3.x | * | V3 成員 |
| V3.x | LIKE 'NPE' | **V1 成員**（特殊規則） |
| V3.x | NOT LIKE 'NPE' | V3 成員 |

**說明：**
- 如果 NodeCodes 同時存在 V1/V2/V3 字眼，需重複統計
- V3.x + NPE 的特殊規則：歸類到 V1 成員列表

---

#### 維度篩選邏輯

##### Plant 篩選
- 直接篩選 `Plant` 欄位對應值

##### Factory 篩選
- 篩選 `MFG_PLANT_CODES` 欄位
- `MFG_PLANT_CODES` 可能包含多個值（如 `NPE,PF,POT`）
- 只要包含其中一個廠區就要計算
- 例：當 Factory 篩選 NPE 或 PF 或 POT 時，皆需納入

##### Line 篩選
- 資料來源：`bronze.common_process_role_user_mapping`（崗位派工）
- 由 `Plant` / `Factory` / `LineName` 篩選條件統計對應人名並去重

---

#### 多 Factory 人員去重規則（僅適用 Config Users）

| 篩選條件 | 是否去重 | 計算單位 |
|---------|---------|---------|
| 包含 Factory（如 V3-CNS-DG3-NPE） | 不去重 | 使用者 × Factory |
| 不包含 Factory（如 V3-CNS-DG3） | 去重 | 使用者 |

**範例：**
```
員工 908903 對應 FAN1 和 FAN2：

篩選 V3-CNS-DG3-FAN1 → 908903 在 FAN1 算 1 次
篩選 V3-CNS-DG3-FAN2 → 908903 在 FAN2 算 1 次
篩選 V3-CNS-DG3      → 908903 去重只算 1 次
```

---

#### 資料來源與關聯

```
Active Users 計算
─────────────────
bronze.common_flowable_task_stats
    ├── TaskDefinitionKey → 判斷 Vx
    ├── TaskStatus → 'Done' 或 'Doing'
    └── TaskAssigneeName → 人員名稱（去重）

Config Users 計算
─────────────────
bronze.common_emp_node_role_mapping
    ├── EmpCode → 員工代碼
    ├── NodeCode → 判斷 V1.x / V2.x / V3.x
    └── Vx → V1/V2/V3

bronze.common_emp_org_info_mapping
    ├── EmpCode → 員工代碼
    ├── Plant → 產品線
    └── MFGFactoryId → MFG_PLANT_CODES

bronze.common_emp_user_group_mapping
    ├── EmpCode → 員工代碼
    └── UserGroupId → 群組 ID

bronze.common_user_group
    └── UserGroupName → User/PMUser/PowerUser 等

bronze.common_process_role_user_mapping（Line 篩選用）
    ├── Plant
    ├── Factory
    └── LineName
```

---

#### 執行流程

```
1. 建立 Config Users 成員列表
   ├── 從 emp_node_role_mapping 取得 NodeCodes
   ├── 從 emp_org_info_mapping 取得 MFG_PLANT_CODES
   ├── 從 emp_user_group_mapping + user_group 取得身分
   ├── 套用 V1/V2/V3 歸屬規則
   ├── 套用 UserGroupName 白名單/排除規則
   └── 依 Plant/Factory/Line 篩選並去重
           │
           ▼
2. 計算 Active Users
   ├── 從 common_flowable_task_stats 取得
   ├── TaskStatus = 'Done' 或 'Doing'
   ├── TaskDefinitionKey 包含 V1/V2/V3
   ├── 人員必須存在於 Config Users 成員列表中
   └── 依去重規則處理
           │
           ▼
3. 計算使用率
   └── Active Users / Config Users
```
