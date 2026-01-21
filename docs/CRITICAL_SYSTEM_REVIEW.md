# 🚨 系統設計重大問題評估報告

## 問題背景

根據 2026-01-21 收到的「Flowable 製造五階與 V1 資料來源規則說明」，發現當前系統設計存在重大問題。

## 核心問題

### 1. ACT_HI_VARINST 使用限制違反 ❌

**規則**：只有 V1 類型的 Process 與 Task 會將變數寫入 `ACT_HI_VARINST`

**當前系統問題**：
- `scripts/transform_silver_generic_metrics.py` 對所有任務都 JOIN `ACT_HI_VARINST`
- V2/V3 任務的 `varinst_moNumber` 實際上是 NULL
- 我們的 V1/V3 歸屬邏輯基於錯誤假設

**影響評估**：
- 🔴 **嚴重**：V1/V3 歸屬邏輯可能完全錯誤
- 🔴 **嚴重**：工單號判斷邏輯對 V2/V3 無效
- 🔴 **嚴重**：所有基於 `varinst_moNumber` 的邏輯都有問題

### 2. 製造五階結構不完整 ❌

**規則**：製造五階 = Region → Vx → Plant → Factory → Line

**當前系統問題**：
- 只有 Plant/Factory/Line（來自 Flowable）
- 缺少 Region 和 Vx 維度
- 未串接 MDM 主檔表

**影響評估**：
- 🟡 **中等**：維度分析不完整
- 🟡 **中等**：無法支援完整的製造五階分析
- 🟡 **中等**：Gold 層指標維度受限

### 3. 資料母體範圍錯誤 ❌

**規則**：依賴 ACT_HI_VARINST 的分析僅限 V1 流程

**當前系統問題**：
- 我們將所有 V1/V2/V3 任務都納入分析
- 但實際上只有 V1 任務有完整的變數資料
- V2/V3 任務缺少關鍵維度資訊

**影響評估**：
- 🔴 **嚴重**：資料母體定義錯誤
- 🔴 **嚴重**：分析結果可能誤導業務決策
- 🔴 **嚴重**：系統架構需要重新設計

## 緊急修正計畫

### Phase 1: 立即驗證 (1-2 天)

1. **驗證 ACT_HI_VARINST 資料分布**
   ```sql
   -- 檢查各 Vx 類型在 ACT_HI_VARINST 中的分布
   SELECT 
       LEFT(hti.TASK_DEF_KEY_, 2) as vx_type,
       COUNT(DISTINCT hti.ID_) as total_tasks,
       COUNT(DISTINCT var.PROC_INST_ID_) as tasks_with_varinst,
       ROUND(COUNT(DISTINCT var.PROC_INST_ID_) * 100.0 / COUNT(DISTINCT hti.ID_), 2) as coverage_pct
   FROM ACT_HI_TASKINST hti
   LEFT JOIN ACT_HI_VARINST var ON hti.PROC_INST_ID_ = var.PROC_INST_ID_
   GROUP BY LEFT(hti.TASK_DEF_KEY_, 2)
   ORDER BY vx_type
   ```

2. **檢查 MDM 主檔表可用性**
   - 確認 `APP_SRV_COMMON.dbo.MDM_*` 表是否存在
   - 評估資料完整性和品質

3. **重新評估當前 V1/V3 歸屬邏輯**
   - 如果 V3 任務沒有 `varinst_moNumber`，歸屬邏輯如何運作？
   - 驗證我們修正的邏輯是否基於錯誤假設

### Phase 2: 架構重新設計 (3-5 天)

1. **重新定義資料範圍**
   - Silver 層分為 V1 專用表和通用表
   - V1 表：包含完整變數和維度資訊
   - 通用表：基本任務資訊，不依賴 ACT_HI_VARINST

2. **建立完整製造五階**
   - 串接所有 MDM 主檔表
   - 建立 Region → Vx → Plant → Factory → Line 完整結構
   - 更新 Silver 層表結構

3. **修正 Gold 層邏輯**
   - 重新設計 L5 指標，明確限定 V1 流程
   - 建立多 Vx 支援的指標架構
   - 更新 REFRESHABLE MV 邏輯

### Phase 3: 系統重建 (5-7 天)

1. **重建 Silver 層**
   - 新的表結構和轉換邏輯
   - 完整的 MDM 串接
   - 正確的資料範圍定義

2. **重建 Gold 層**
   - 基於正確資料範圍的指標
   - 完整製造五階支援
   - 更新自動化機制

3. **重新驗證**
   - 端到端資料驗證
   - 業務邏輯驗證
   - 效能測試

## 風險評估

### 高風險
- 🔴 **當前所有分析結果可能錯誤**
- 🔴 **需要重新驗證所有已完成的工作**
- 🔴 **系統架構需要重大調整**

### 中風險
- 🟡 **開發時程延長 1-2 週**
- 🟡 **需要重新學習 MDM 主檔結構**
- 🟡 **Gold 層自動化機制需要重建**

### 低風險
- 🟢 **Bronze 層同步邏輯不受影響**
- 🟢 **基礎設施和工具可以重用**
- 🟢 **驗證腳本架構可以保留**

## 建議行動

### 立即行動 (今天)
1. ✅ 建立此評估報告
2. ⚠️ 暫停當前 Gold 層相關開發
3. ⚠️ 開始驗證 ACT_HI_VARINST 資料分布

### 短期行動 (本週)
1. 完成資料來源驗證
2. 重新設計系統架構
3. 建立新的開發計畫

### 中期行動 (下週)
1. 重建 Silver 層
2. 重建 Gold 層
3. 重新驗證所有邏輯

## 結論

這是一個重大的系統設計問題，需要立即處理。雖然會延長開發時程，但確保系統正確性比快速交付更重要。

**下一步**：立即開始驗證 ACT_HI_VARINST 資料分布，確認問題範圍。

---
**建立日期**：2026-01-21  
**優先級**：🚨 最高  
**狀態**：待處理