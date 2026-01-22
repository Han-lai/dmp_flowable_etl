# L5 指標 MDM 五階維度更新方案

**版本：** 1.0  
**更新日期：** 2026-01-21  
**目標：** 將 L5 指標從三維度（Plant/Factory/Line）升級為五維度（Region/Vx/Plant/Factory/Line）

---

## 📊 現狀分析

### 現有 L5 指標結構
```sql
-- 現有維度
plant, factory, line

-- 缺失維度
region (MFG_SITE), vx_code
```

### 現有表結構
| 表名 | 維度 | 用途 |
|------|------|------|
| `gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT` | plant, factory, line | L5 任務完成率快照 |
| `silver.mv_l5_metrics_realtime` | plant, factory, line | L5 指標實時聚合 |
| `silver.mv_fact_task_vx_attribution` | plant, factory, line | 任務事實表 |

---

## 🔄 更新方案

### 第一步：更新 Silver 層事實表

#### 目標
在 `silver.mv_fact_task_vx_attribution` 中加入五階維度欄位

#### 新增欄位
```sql
-- 五階維度欄位
region_code String,           -- 由 MDM_FACTORY_AREA_MASTER.MFG_SITE 提供
region_name String,           -- Region 描述名稱
vx_code String,               -- V1/V2/V3（業務邏輯）
vx_name String,               -- Vx 描述
plant_code String,            -- 由 MDM_MFG_PLANT_MASTER 提供
plant_name String,            -- Plant 描述
factory_code String,          -- 由 MDM_FACTORY_AREA_MASTER 提供
factory_name String,          -- Factory 描述
line_code String,             -- 由 MDM_LINE_DESC_MASTER 提供
line_name String              -- Line 描述
```

#### 實施方式
```sql
-- 從 dim_mfg_five_level 維度表 JOIN 任務事實表
SELECT 
    t.*,
    -- 五階維度
    d.region_code,
    d.region_name,
    t.vx_type as vx_code,
    CASE t.vx_type 
        WHEN 'V1' THEN 'Version 1'
        WHEN 'V2' THEN 'Version 2'
        WHEN 'V3' THEN 'Version 3'
        ELSE 'Unknown'
    END as vx_name,
    d.plant_code,
    d.plant_name,
    d.factory_code,
    d.factory_name,
    d.line_code,
    d.line_desc as line_name
FROM silver.mv_fact_task_vx_attribution t
LEFT JOIN silver.dim_mfg_five_level d
    ON t.line = d.line_code
```

### 第二步：更新 Silver 層 L5 指標聚合

#### 目標
在 `silver.mv_l5_metrics_realtime` 中加入五階維度分組

#### 新增分組維度
```sql
-- 原有分組
GROUP BY snapshot_date, vx_type, vx_subtype, plant, factory, line

-- 新增分組
GROUP BY snapshot_date, vx_type, vx_subtype, 
         region_code, region_name,
         plant_code, plant_name,
         factory_code, factory_name,
         line_code, line_name
```

#### 新增欄位
```sql
-- 五階維度欄位
region_code String,
region_name String,
plant_code String,
plant_name String,
factory_code String,
factory_name String,
line_code String,
line_name String
```

### 第三步：更新 Gold 層 L5 指標快照

#### 目標
在 `gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT` 中加入五階維度

#### 新增欄位
```sql
-- 五階維度欄位
region_code String,
region_name String,
plant_code String,
plant_name String,
factory_code String,
factory_name String,
line_code String,
line_name String
```

#### 新增 ORDER BY 欄位
```sql
-- 原有 ORDER BY
ORDER BY (snapshot_date, vx_type, vx_subtype, plant, factory, line, ...)

-- 新增 ORDER BY
ORDER BY (snapshot_date, vx_type, vx_subtype, 
          region_code, plant_code, factory_code, line_code, ...)
```

---

## 📈 L5 指標計算邏輯更新

### 現有邏輯
```sql
-- 按 Plant/Factory/Line 分組計算
SELECT 
    snapshot_date,
    vx_type,
    plant,
    factory,
    line,
    COUNT(*) as total_task_qty,
    COUNTIF(task_status = 'DONE') as done_qty,
    done_qty / total_task_qty as completion_rate
FROM silver.mv_fact_task_vx_attribution
GROUP BY snapshot_date, vx_type, plant, factory, line
```

### 新邏輯（五階維度）
```sql
-- 按五階維度分組計算
SELECT 
    snapshot_date,
    vx_type,
    region_code,
    region_name,
    plant_code,
    plant_name,
    factory_code,
    factory_name,
    line_code,
    line_name,
    COUNT(*) as total_task_qty,
    COUNTIF(task_status = 'DONE') as done_qty,
    COUNTIF(task_status = 'TODO') as todo_qty,
    COUNTIF(task_status = 'DOING') as doing_qty,
    done_qty / total_task_qty as completion_rate
FROM silver.mv_fact_task_vx_attribution
WHERE region_code IS NOT NULL
  AND plant_code IS NOT NULL
  AND factory_code IS NOT NULL
  AND line_code IS NOT NULL
GROUP BY snapshot_date, vx_type, 
         region_code, region_name,
         plant_code, plant_name,
         factory_code, factory_name,
         line_code, line_name
```

---

## 🎯 指標定義更新

### L5 任務完成率（五階維度版）

**定義：** 在特定五階維度組合（Region/Vx/Plant/Factory/Line）下，已完成任務數 / 總任務數

**計算公式：**
```
L5_Completion_Rate = DONE_Tasks / Total_Tasks × 100%
```

**維度：**
- Region（由 MFG_SITE 提供）
- Vx（V1/V2/V3）
- Plant（由 MDM_MFG_PLANT_MASTER 提供）
- Factory（由 MDM_FACTORY_AREA_MASTER 提供）
- Line（由 MDM_LINE_DESC_MASTER 提供）

**時間粒度：**
- 日級別（Daily）
- 周級別（Weekly）
- 月級別（Monthly）
- 累計（Total）

**篩選條件：**
- 僅包含 V1 流程（根據 metric_definitions.md 規則）
- 排除 is_excluded = 1 的任務
- 五階維度完整（region_code, plant_code, factory_code, line_code 都不為 NULL）

---

## 📋 實施步驟

### 步驟 1：驗證 MDM 五階維度表
- [x] ✅ 已完成：`silver.dim_mfg_five_level` 已建立
- [x] ✅ 已驗證：9,492 條產線，94.92% 有效率

### 步驟 2：更新 Silver 層事實表
- [ ] 待執行：在 `silver.mv_fact_task_vx_attribution` 中加入五階維度欄位
- [ ] 待執行：從 `dim_mfg_five_level` JOIN 任務資料

### 步驟 3：更新 Silver 層 L5 指標聚合
- [ ] 待執行：更新 `silver.mv_l5_metrics_realtime` 的分組維度
- [ ] 待執行：新增五階維度欄位

### 步驟 4：更新 Gold 層 L5 指標快照
- [ ] 待執行：更新 `gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT` 結構
- [ ] 待執行：重新計算歷史快照

### 步驟 5：驗證與測試
- [ ] 待執行：驗證 V1-CNE-WJ2-PF-E5 的 L5 指標
- [ ] 待執行：比較新舊邏輯的計算結果
- [ ] 待執行：更新 Cube.js 查詢邏輯

---

## 🔗 相關文件

- `docs/mdm_five_level_implementation_summary.md` - MDM 五階實施總結
- `docs/metric_definitions.md` - 指標定義
- `sql/create_silver_dim_mfg_five_level.sql` - 五階維度表
- `sql/12_create_silver_mviews_layer2.sql` - Silver 層 MVIEW

---

## ⚠️ 注意事項

1. **資料完整性**：L5 指標僅計算五階維度完整的任務
2. **V1 限制**：根據 metric_definitions.md，L5 指標僅限 V1 流程
3. **向後相容**：保留原有的 plant/factory/line 欄位以支援現有查詢
4. **效能考量**：新增維度可能影響查詢效能，建議建立適當索引

---

**結論**：L5 指標升級為五階維度後，將提供更細粒度的製造流程分析能力，支援按 Region/Vx/Plant/Factory/Line 多維度分析任務完成率。