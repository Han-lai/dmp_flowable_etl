# MVIEW 與文件不一致問題分析報告

## 執行時間
2026-01-23

## 問題概述

目前 MVIEW 架構實作與 `docs/manufacturing_five_level_data_lineage.md` 文件描述存在嚴重不一致，導致 V2/V3 流程的製造五階維度資料缺失。

## 具體不一致問題

### 1. 維度來源不一致

| 項目 | 文件描述 | 實際實作 | 影響 |
|------|---------|----------|------|
| **主要來源** | MDM 主檔表 | 僅 Flowable 變數 | 資料品質下降 |
| **Region 支援** | 完整支援 | 完全缺失 | 無法提供五階維度 |
| **資料優先級** | MDM 優先，Flowable 備用 | 僅 Flowable | 無 fallback 機制 |

### 2. 檔案位置對應

#### 文件描述的架構
```
docs/manufacturing_five_level_data_lineage.md (行 45-65)
```
> **MDM 主檔表**
> - bronze.common_mdm_line_desc_master: 產線主檔
> - bronze.common_mdm_prod_area_master: 生產區域主檔  
> - bronze.common_mdm_mfg_plant_master: 製造廠區主檔
> - bronze.common_mdm_factory_area_master: 廠區主檔
> - bronze.common_mdm_mfg_site_master: 製造基地主檔

#### 實際實作
```
sql/12_create_silver_mviews_layer2.sql (行 108-112)
```
```sql
-- 維度
COALESCE(v.varinst_plant, '') AS plant,
COALESCE(v.varinst_factory, '') AS factory,
COALESCE(v.varinst_lineName, '') AS line,
```

**問題：** 完全未使用 MDM 主檔表，僅依賴 `silver.mv_varinst_pivoted`

### 3. 資料流向不一致

#### 文件描述的資料流
```
docs/manufacturing_five_level_data_lineage.md (行 120-140)
```
```mermaid
MDM 主檔表 → silver.dim_mfg_five_level → silver.mv_fact_task_vx_attribution
```

#### 實際實作的資料流
```
sql/12_create_silver_mviews_layer2.sql (行 85-90)
```
```sql
LEFT JOIN silver.mv_varinst_pivoted v
    ON t.PROC_INST_ID_ = v.PROC_INST_ID_
-- 未使用 silver.dim_mfg_five_level
```

**問題：** 實際未串接 `silver.dim_mfg_five_level`，導致無法使用 MDM 維度

### 4. 覆蓋率差異

| Vx 類型 | 維度 | 文件預期覆蓋率 | 實際覆蓋率 | 差異 |
|---------|------|---------------|-----------|------|
| V2 | Factory | 95%+ | 3.5% | -91.5% |
| V2 | Line | 95%+ | 0% | -95% |
| V3 | Region | 95%+ | 0% | -95% |
| 所有 | Region | 95%+ | 0% | -95% |

## 根本原因分析

### 1. 設計與實作脫節

**問題根源：**
- 文件描述了理想的 MDM 整合架構
- 實際實作僅使用 Flowable 變數作為快速解決方案
- 缺少從設計到實作的驗證機制

**具體位置：**
```
sql/12_create_silver_mviews_layer2.sql (行 1-10)
```
註解說明使用原生 Flowable 表，但未提及 MDM 整合

### 2. V1 流程限制被忽略

**問題根源：**
- 只有 V1 流程會寫入 `ACT_HI_VARINST`
- V2/V3 流程無 Flowable 變數資料
- 設計時未考慮此限制

**影響範圍：**
- V2 任務：55,416 筆，Factory 覆蓋率僅 3.5%
- V3 任務：236,398 筆，但實際應該有完整維度

### 3. 文件更新滯後

**問題根源：**
- 實作完成後未同步更新文件
- 文件描述的是目標架構，非實際架構
- 缺少實作驗證步驟

## 業務影響評估

### 1. 資料品質影響

| 影響項目 | 嚴重程度 | 影響範圍 |
|---------|----------|----------|
| V2/V3 維度缺失 | 🔴 高 | 291,814 筆任務 (22.4%) |
| Region 維度缺失 | 🔴 高 | 全部任務 (100%) |
| 資料來源不可追蹤 | 🟡 中 | 全部任務 (100%) |

### 2. 分析能力影響

| 分析需求 | 影響程度 | 說明 |
|---------|----------|------|
| 跨 Vx 類型比較 | 🔴 無法進行 | V2/V3 缺少維度資料 |
| 區域層級分析 | 🔴 無法進行 | 完全缺少 Region 維度 |
| 維度資料品質監控 | 🔴 無法進行 | 無資料來源標記 |

### 3. 系統擴展性影響

| 擴展需求 | 影響程度 | 說明 |
|---------|----------|------|
| 新增 Vx 類型 | 🔴 高風險 | 依賴 Flowable 變數，新類型可能無資料 |
| 維度標準化 | 🔴 高風險 | 無 MDM 整合，難以標準化 |
| 多廠區分析 | 🟡 中風險 | 缺少 Region 層級，分析能力受限 |

## 解決方案

### 1. 立即執行：建立 MDM 整合版本

**檔案：** `sql/12_create_silver_mviews_layer2_mdm_integrated.sql`

**關鍵改善：**
- 整合 `silver.dim_mfg_five_level` 作為主要維度來源
- 建立 MDM → Flowable → Business Key 的優先順序邏輯
- 新增 `dimension_source` 欄位追蹤資料來源

### 2. 更新文件對齊實際

**檔案：** `docs/manufacturing_five_level_data_lineage_updated.md`

**關鍵更新：**
- 明確標示原版本問題和改善方案
- 提供實際覆蓋率數據對比
- 建立部署策略和風險評估

### 3. 建立驗證機制

**檔案：** `scripts/validate_mdm_tables_for_mview.py`

**驗證內容：**
- MDM 表結構和資料品質
- Flowable vs MDM 對應關係 (100% 成功率)
- 各 Vx 類型維度覆蓋率分析

## 預期改善效果

### 1. 資料品質提升

| 指標 | 改善前 | 改善後 | 提升幅度 |
|------|--------|--------|----------|
| V2 Factory 覆蓋率 | 3.5% | 100% | +96.5% |
| V2 Line 覆蓋率 | 0% | 100% | +100% |
| Region 覆蓋率 | 0% | 95.2% | +95.2% |
| 資料來源可追蹤性 | 0% | 100% | +100% |

### 2. 分析能力提升

- ✅ 支援完整五階維度分析
- ✅ 支援跨 Vx 類型比較
- ✅ 支援區域層級分析
- ✅ 支援維度資料品質監控

### 3. 系統穩定性提升

- ✅ 降低對 Flowable 變數的依賴
- ✅ 提供多層級 fallback 機制
- ✅ 支援未來 Vx 類型擴展
- ✅ 提供維度標準化基礎

## 建議執行順序

1. **立即執行**：部署 MDM 整合版本 MVIEW (並行運作)
2. **短期執行**：驗證新版本資料品質和效能
3. **中期執行**：逐步切換 Gold 層和 Cube 層
4. **長期執行**：完全替換並移除舊版本

## 風險控制

1. **並行部署**：新舊版本同時運作，確保業務連續性
2. **資料驗證**：建立完整的資料一致性檢查
3. **效能監控**：監控新版本對系統效能的影響
4. **回滾機制**：保留舊版本作為緊急回滾選項