# L5 指標五階維度實施完成報告

**實施日期：** 2026-01-21  
**狀態：** ✅ 完成

---

## 📊 實施概要

### 目標
將 L5 指標從三維度（Plant/Factory/Line）升級為五維度（Region/Vx/Plant/Factory/Line），使用 MDM 主檔表提供的標準化維度。

### 完成情況
✅ Silver 層五階維度增強視圖已建立  
✅ L5 指標聚合已升級為五維度  
✅ 資料驗證完成，85.77% 任務具有完整五階維度

---

## 🔄 實施內容

### 1. Silver 層五階維度增強視圖

**視圖名稱：** `silver.vw_fact_task_with_five_level`

**功能：** 將任務事實表與 MDM 五階維度表進行 JOIN，為每個任務補齊五階維度資訊

**新增欄位：**
```sql
region_code          -- 由 MDM_FACTORY_AREA_MASTER.MFG_SITE 提供
region_name          -- Region 描述名稱
vx_code              -- V1/V2/V3
vx_name              -- Vx 描述
plant_code           -- 由 MDM_MFG_PLANT_MASTER 提供
plant_name           -- Plant 描述
factory_code         -- 由 MDM_FACTORY_AREA_MASTER 提供
factory_name         -- Factory 描述
line_code            -- 由 MDM_LINE_DESC_MASTER 提供
line_name            -- Line 描述
five_level_complete  -- 五階維度完整性標記 (0/1)
```

**資料統計：**
- 總任務數：1,300,963 筆
- 五階完整任務：1,115,818 筆
- 完整率：85.77%

### 2. L5 指標聚合視圖

**視圖名稱：** `silver.vw_l5_metrics_five_level`

**功能：** 按五階維度分組聚合任務統計，計算 L5 指標

**分組維度：**
```sql
snapshot_date        -- 快照日期
vx_type              -- V1/V2/V3
vx_subtype           -- V1_NPE/V1_MFG/空字串
region_code          -- Region 代碼
region_name          -- Region 名稱
plant_code           -- Plant 代碼
plant_name           -- Plant 名稱
factory_code         -- Factory 代碼
factory_name         -- Factory 名稱
line_code            -- Line 代碼
line_name            -- Line 名稱
```

**計算指標：**
```sql
total_task_qty       -- 總任務數
todo_qty             -- TODO 狀態任務數
doing_qty            -- DOING 狀態任務數
done_qty             -- DONE 狀態任務數
doing_done_qty       -- DOING + DONE 任務數
todo_doing_acc_qty   -- TODO + DOING 任務數
excluded_qty         -- 排除任務數
five_level_complete_qty    -- 五階完整任務數
five_level_incomplete_qty  -- 五階不完整任務數
```

**聚合統計：**
- 指標行數：6,236 行
- 唯一日期：92 天
- 唯一 Region：5 個
- 唯一 Plant：8 個
- 唯一 Factory：10 個
- 唯一 Line：101 條

### 3. 指標計算邏輯

#### 任務完成率
```
Completion_Rate = DONE_Tasks / Total_Tasks × 100%
```

#### 五階維度完整性
```
Five_Level_Complete_Rate = Five_Level_Complete_Tasks / Total_Tasks × 100%
```

#### 任務狀態分布
```
TODO_Rate = TODO_Tasks / Total_Tasks × 100%
DOING_Rate = DOING_Tasks / Total_Tasks × 100%
DONE_Rate = DONE_Tasks / Total_Tasks × 100%
```

---

## 📈 資料品質分析

### 五階維度完整性

| 指標 | 數值 |
|------|------|
| 總任務數 | 1,300,963 |
| 五階完整任務 | 1,115,818 |
| 完整率 | 85.77% |
| 不完整任務 | 185,145 |

### 維度分布

| 維度 | 唯一值數 | 說明 |
|------|---------|------|
| Region | 5 | DG, CZ, WJ, BPO, WG |
| Plant | 8 | 8 個不同的 Plant |
| Factory | 10 | 10 個不同的 Factory |
| Line | 101 | 101 條不同的產線 |
| Date | 92 | 92 天的資料 |

### 任務狀態分布

| 狀態 | 任務數 | 百分比 |
|------|--------|--------|
| TODO | - | - |
| DOING | - | - |
| DONE | - | - |

---

## 🎯 L5 指標定義（五階維度版）

### 指標名稱
**L5 任務完成率（五階維度）**

### 定義
在特定五階維度組合（Region/Vx/Plant/Factory/Line）下，已完成任務數占總任務數的比例。

### 計算公式
```
L5_Completion_Rate = DONE_Tasks / Total_Tasks × 100%
```

### 維度
- **Region**：由 MDM_FACTORY_AREA_MASTER.MFG_SITE 提供
- **Vx**：V1/V2/V3（業務邏輯決定）
- **Plant**：由 MDM_MFG_PLANT_MASTER 提供
- **Factory**：由 MDM_FACTORY_AREA_MASTER 提供
- **Line**：由 MDM_LINE_DESC_MASTER 提供

### 時間粒度
- 日級別（Daily）
- 周級別（Weekly）
- 月級別（Monthly）
- 累計（Total）

### 篩選條件
- 僅包含 V1 流程（根據 metric_definitions.md 規則）
- 排除 is_excluded = 1 的任務
- 五階維度完整（region_code, plant_code, factory_code, line_code 都不為 NULL）

---

## 🔗 相關文件

- `docs/mdm_five_level_implementation_summary.md` - MDM 五階實施總結
- `docs/l5_metrics_mdm_five_level_update.md` - L5 指標更新方案
- `sql/update_l5_metrics_with_five_level.sql` - 實施 SQL
- `sql/create_silver_dim_mfg_five_level.sql` - 五階維度表

---

## ✅ 驗證清單

- [x] Silver 層五階維度增強視圖已建立
- [x] L5 指標聚合視圖已升級為五維度
- [x] 資料品質驗證完成（85.77% 完整率）
- [x] 具體範例驗證（WJ-WJ2-PF-E5）
- [x] 指標計算邏輯已更新

---

## 🚀 後續建議

### 立即可執行
1. ✅ 已完成：Silver 層五階維度增強視圖
2. ✅ 已完成：L5 指標聚合視圖升級
3. 待執行：更新 Cube.js 查詢邏輯以使用新視圖

### 中期規劃
1. 建立 Gold 層五階維度快照表
2. 更新儀表板查詢以支援五階維度分析
3. 建立五階維度的資料品質監控

### 長期規劃
1. 完全替換舊的三維度 L5 指標
2. 建立五階維度的歷史快照
3. 實施五階維度的版本管理

---

**結論**：L5 指標已成功升級為五階維度，提供更細粒度的製造流程分析能力。85.77% 的任務具有完整五階維度，可以支援按 Region/Vx/Plant/Factory/Line 多維度分析任務完成率。