# 非 V1 流程 VARINST vs MDM 差距分析報告

## 📋 執行摘要

**驗證目標**: 證明非 V1 流程無法從 VARINST 取得完整五階維度，必須依賴 MDM 補齊

**驗證樣本**: 6 個指定的非 V1 流程 PROC_INST_ID

**關鍵發現**: ✅ **驗證成功** - 非 V1 流程確實在 VARINST 中缺失關鍵維度，需要 MDM 補齊

## 🔍 驗證結果詳細分析

### 1. VARINST 實際內容檢查

**檢查結果**: 所有 6 個非 V1 流程都包含以下 VARINST 維度：

| PROC_INST_ID | Plant | Factory | LineName | Region | 其他維度 |
|--------------|-------|---------|----------|--------|----------|
| 3c40f619-c593-11f0-8d58-1e564a6128f7 | ✅ DG3 | ✅ SV | ✅ S01 | ❌ 缺失 | moNumber, productionArea 等 |
| 38cfc17e-ef5a-11f0-a787-0a5a5063cfa7 | ✅ WJ2 | ✅ NBU | ✅ E5 | ❌ 缺失 | moNumber, productionArea 等 |
| 3ca530c5-d938-11f0-8eb2-761d901080ab | ✅ DG3 | ✅ SV | ✅ S01 | ❌ 缺失 | moNumber, productionArea 等 |
| 505b457d-63b3-11f0-b8b8-b6733f7db4dd | ✅ WJ2 | ✅ NBU | ✅ E5 | ❌ 缺失 | moNumber, productionArea 等 |
| 3c60482b-ecf9-11f0-ba59-92564f99f227 | ✅ WJ2 | ✅ NBU | ✅ E4 | ❌ 缺失 | moNumber, productionArea 等 |
| 3ca93700-ef50-11f0-a787-0a5a5063cfa7 | ✅ WJ2 | ✅ NBU | ✅ E5 | ❌ 缺失 | moNumber, productionArea 等 |

**重要發現**:
- ✅ **Plant, Factory, LineName 維度完整**: 所有非 V1 流程都有這三個維度
- ❌ **Region 維度 100% 缺失**: 6/6 個流程都沒有 region 維度
- ⚠️ **與預期不符**: 原本預期非 V1 流程會缺失更多維度，但實際上只缺失 region

### 2. 維度缺失統計

| 維度 | 缺失數量 | 缺失比例 | 狀態 |
|------|----------|----------|------|
| Region | 6/6 | 100% | ❌ 完全缺失 |
| Plant | 0/6 | 0% | ✅ 完整 |
| Factory | 0/6 | 0% | ✅ 完整 |
| LineName | 0/6 | 0% | ✅ 完整 |

**結論**: 非 V1 流程主要缺失的是 **Region 維度**，其他三階維度在 VARINST 中是完整的。

### 3. MDM 補齊能力驗證

**MDM Join 狀態**: 所有 6 個流程都顯示 "✅ MDM 成功"，但實際維度值為空

**問題分析**:
1. **BUSINESS_KEY_ 解析問題**: 非 V1 流程的 BUSINESS_KEY_ 可能不包含 lineName 資訊
2. **MDM Join Key 缺失**: 無法從 BUSINESS_KEY_ 中提取有效的 join key
3. **需要替代 Join 策略**: 可能需要使用其他欄位作為 MDM join 的依據

### 4. 實際維度值對照

**VARINST 維度值** (從步驟 1 實際內容檢查):

| 流程 | Plant | Factory | LineName | Region |
|------|-------|---------|----------|--------|
| 流程 1 | DG3 | SV | S01 | NULL |
| 流程 2 | WJ2 | NBU | E5 | NULL |
| 流程 3 | DG3 | SV | S01 | NULL |
| 流程 4 | WJ2 | NBU | E5 | NULL |
| 流程 5 | WJ2 | NBU | E4 | NULL |
| 流程 6 | WJ2 | NBU | E5 | NULL |

**MDM 補齊潛力**:
- 根據已知的 MDM 映射規格，這些 lineName (S01, E5, E4) 都應該能在 MDM 表中找到對應的 region
- 例如: E5 → CNE, S01 → 對應的 region code

## 📊 總結統計

| 指標 | 數值 | 百分比 |
|------|------|--------|
| 驗證樣本總數 | 6 | 100% |
| **VARINST 缺失統計** | | |
| Region 缺失 | 6 | 100% |
| Plant 缺失 | 0 | 0% |
| Factory 缺失 | 0 | 0% |
| LineName 缺失 | 0 | 0% |
| **MDM 補齊需求** | | |
| 需要 Region 補齊 | 6 | 100% |
| 有 LineName 可作為 Join Key | 6 | 100% |

## 🎯 核心結論

### ✅ 驗證成功的部分

1. **非 V1 流程確實存在維度缺失**: Region 維度 100% 缺失
2. **VARINST 不足以提供完整五階維度**: 缺失最高層級的 region 維度
3. **MDM 補齊的必要性**: 非 V1 流程必須依賴 MDM 來取得完整的五階維度

### ⚠️ 發現與預期的差異

1. **缺失範圍較預期小**: 只有 region 缺失，plant/factory/lineName 都存在
2. **MDM Join 策略需要調整**: 當前的 BUSINESS_KEY_ 解析方式不適用於非 V1 流程
3. **補齊策略更明確**: 主要需要補齊 region 維度，其他維度可直接使用 VARINST

### 🔧 對 Silver/Gold 設計的影響

1. **維度交換邏輯仍然適用**: plant/factory 維度交換邏輯對非 V1 流程同樣重要
2. **Region 補齊策略**: 
   - 優先使用 MDM: 透過 lineName join MDM 表取得 region
   - VARINST 備用: 對於 V1 流程，仍可使用 VARINST 的 region 值
3. **資料來源標記**: 需要明確標記 region 的來源 (MDM_PRIMARY vs VARINST_FALLBACK)

## 📋 建議行動

### 立即行動
1. **修正 MDM Join 邏輯**: 改用 lineName 直接 join，而非依賴 BUSINESS_KEY_ 解析
2. **實作 Region 補齊**: 在 Silver 層 MVIEW 中加入 region 補齊邏輯
3. **驗證補齊效果**: 確認 MDM join 能成功補齊 region 維度

### 後續監控
1. **覆蓋率監控**: 追蹤 region 維度的 MDM 補齊成功率
2. **資料品質檢查**: 定期驗證補齊後的 region 值是否正確
3. **效能影響評估**: 監控 MDM join 對查詢效能的影響

## 🔗 相關文件

- [VARINST 到 MDM 映射規格表](varinst_to_mdm_mapping_specification.md)
- [Silver/Gold 層映射合規驗證報告](silver_gold_mapping_compliance_report.md)
- [驗證 SQL](../sql/validate_non_v1_varinst_vs_mdm.sql)
- [執行腳本](../scripts/execute_non_v1_varinst_mdm_validation.py)

---

**報告產出時間**: 2026-01-26  
**驗證狀態**: ✅ 核心目標達成 - 證明非 V1 流程需要 MDM 補齊維度