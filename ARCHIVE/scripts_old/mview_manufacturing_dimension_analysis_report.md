# MVIEW 製造五階維度分析報告

## 執行時間
2026-01-23

## 分析目的
檢查目前 MVIEW 架構（已更新為使用原生 Flowable 表）是否使用了 MDM 主檔表作為製造五階維度的來源。

## 關鍵發現

### ❌ 主要問題：MVIEW 未使用 MDM 主檔表

**目前 MVIEW 維度來源：**
- `plant`: 來自 `silver.mv_varinst_pivoted.varinst_plant` (Flowable 變數)
- `factory`: 來自 `silver.mv_varinst_pivoted.varinst_factory` (Flowable 變數)  
- `line`: 來自 `silver.mv_varinst_pivoted.varinst_lineName` (Flowable 變數)
- `vx_type`: 業務邏輯推導
- `vx_subtype`: NPE 判別邏輯

**問題分析：**
1. **完全依賴 Flowable 變數**：維度資料 100% 來自 `bronze.bpm_act_hi_varinst`
2. **缺少 Region 層級**：無法提供完整的五階維度 (Region → Vx → Plant → Factory → Line)
3. **未與 MDM 驗證**：無法確保維度資料的標準化和一致性
4. **資料覆蓋率限制**：varinst_pivoted 覆蓋率有限 (Plant: 82%, Factory: 70.6%, Line: 32.4%)

### ✅ MDM 主檔表現況

**可用的 MDM 主檔表：**
- `bronze.common_mdm_line_desc_master`: 16,940 筆產線記錄
- `bronze.common_mdm_prod_area_master`: 840 筆產區記錄  
- `bronze.common_mdm_mfg_plant_master`: 384 筆工廠記錄
- `bronze.common_mdm_factory_area_master`: 103 筆廠區記錄
- `bronze.common_mdm_mfg_site_master`: 10 筆製造基地記錄

**製造五階維度表現況：**
- `silver.dim_mfg_five_level`: 9,492 筆產線記錄，94.9% 有效
- 完整的 Region → Plant → Factory → Line 維度串接
- 95.2% 有 Region 資料，95.0% 有 Plant 資料，100% 有 Factory 資料

### 📊 資料品質對比

| 維度層級 | Flowable 變數覆蓋率 | MDM 主檔覆蓋率 | 差異 |
|---------|-------------------|---------------|------|
| Region  | 0% (無此維度)      | 95.2%         | +95.2% |
| Plant   | 82.0%             | 95.0%         | +13.0% |
| Factory | 70.6%             | 100%          | +29.4% |
| Line    | 32.4%             | 100%          | +67.6% |

## 建議改善方案

### 方案 1：MVIEW 整合 MDM 主檔表 (建議)

**實作步驟：**
1. 修改 `sql/12_create_silver_mviews_layer2.sql`
2. 在 `silver.mv_fact_task_vx_attribution` 中加入 MDM 維度串接
3. 建立 Flowable vs MDM 的一致性檢查邏輯
4. 補齊 Region 層級維度

**優點：**
- 提供完整五階維度
- 提高維度資料品質和覆蓋率
- 與既有 MDM 架構一致
- 支援維度標準化驗證

### 方案 2：建立混合維度邏輯

**實作概念：**
```sql
-- 維度優先順序：MDM 主檔 > Flowable 變數 > 預設值
COALESCE(
    mdm.standardized_plant,     -- MDM 標準化值
    v.varinst_plant,           -- Flowable 原始值
    'UNKNOWN'                  -- 預設值
) AS plant
```

**優點：**
- 最大化資料覆蓋率
- 保持向後相容性
- 提供資料來源追蹤

### 方案 3：建立維度驗證機制

**實作內容：**
1. 建立 Flowable vs MDM 維度對照表
2. 標記維度不一致的記錄
3. 提供資料品質監控報告

## 具體實作建議

### 1. 立即執行：修改 MVIEW SQL

修改 `sql/12_create_silver_mviews_layer2.sql` 中的維度邏輯：

```sql
-- 加入 MDM 維度串接
LEFT JOIN silver.dim_mfg_five_level mdm
    ON COALESCE(v.varinst_lineName, '') = mdm.line_name

-- 修改維度欄位
COALESCE(mdm.region_code, '') AS region,
COALESCE(mdm.plant_code, v.varinst_plant, '') AS plant,
COALESCE(mdm.factory_code, v.varinst_factory, '') AS factory,
COALESCE(mdm.line_name, v.varinst_lineName, '') AS line,

-- 加入資料來源標記
CASE 
    WHEN mdm.line_name IS NOT NULL THEN 'MDM'
    WHEN v.varinst_lineName IS NOT NULL THEN 'FLOWABLE'
    ELSE 'UNKNOWN'
END AS dimension_source
```

### 2. 建立驗證腳本

建立 `scripts/validate_mview_mdm_integration.py` 驗證整合效果。

### 3. 更新文件

更新 `docs/manufacturing_five_level_data_lineage.md` 反映實際實作狀況。

## 結論

目前 MVIEW 架構**未使用 MDM 主檔表**，完全依賴 Flowable 變數作為維度來源。這與文件中描述的五階維度架構不符，需要立即整合 MDM 主檔表以：

1. 提供完整的五階維度 (包含 Region)
2. 提高維度資料品質和覆蓋率  
3. 確保維度標準化和一致性
4. 支援未來的維度擴展需求

**建議優先執行方案 1**，完整整合 MDM 主檔表到 MVIEW 架構中。