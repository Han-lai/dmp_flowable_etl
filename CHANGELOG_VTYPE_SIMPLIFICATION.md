# VTYPE 分類邏輯簡化變更記錄

**變更日期**: 2026-04-15  
**變更類型**: 邏輯簡化 (Logic Simplification)  
**影響範圍**: Silver 層 VTYPE 分類邏輯

---

## 變更摘要

移除冗餘的 VTYPE 分類規則，簡化邏輯並提升可維護性。

### 移除的規則

- ❌ **規則 1**: DG3 + 特定工單號 → V1
- ❌ **規則 2**: NPE + 特定工單號 → V1

### 保留的規則

- ✅ **規則 1** (原規則 3): 特定工單號 → V1
- ✅ **規則 2-4**: TASK_DEF_KEY_ 前綴匹配
- ✅ **規則 5**: 預設

---

## 變更原因

### 1. 規則重疊驗證

**全域驗證結果**:
- 規則 1 (DG3 + 工單號) 符合數: 304,067
- 規則 2 (NPE + 工單號) 符合數: 19,419
- 規則 3 (僅工單號) 符合數: 365,650
- **規則 1 獨立數**: 0 (100% 被規則 3 涵蓋)
- **規則 2 獨立數**: 0 (100% 被規則 3 涵蓋)

**特定線體驗證** (CNS DG3 SMT ST02, 2025-12-25~2025-12-31):
- 總任務數: 5,179
- 差異任務數: 0
- 差異比例: 0%

### 2. 數學證明

```
規則 1 (DG3 + 工單號) ⊆ 規則 3 (僅工單號)
規則 2 (NPE + 工單號) ⊆ 規則 3 (僅工單號)
```

由於規則 3 不檢查廠區條件，只要工單號符合就歸類為 V1，因此完全涵蓋了規則 1 和 2 的所有情況。

---

## 變更前後對比

### 變更前 (2026-04-15 之前)

```sql
CASE 
    -- 規則 1: DG3 + 特定工單號 → V1
    WHEN plant = 'DG3' 
         AND substring(mo_number, 1, 3) IN ('196','199','200','210','212','213') 
    THEN 'V1'
    
    -- 規則 2: NPE + 特定工單號 → V1
    WHEN (factory LIKE '%NPE%' OR plant LIKE '%NPE%')
         AND substring(mo_number, 1, 3) IN ('196','199','200','210','212','213') 
    THEN 'V1'
    
    -- 規則 3: 僅工單號 → V1
    WHEN substring(mo_number, 1, 3) IN ('196','199','200','210','212','213')
    THEN 'V1'
    
    -- 規則 4-6: TASK_DEF_KEY_ 前綴匹配
    WHEN TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
    WHEN TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
    WHEN TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
    
    -- 規則 7: 預設
    ELSE COALESCE(substring(TASK_DEF_KEY_, 1, 2), 'Unknown')
END
```

### 變更後 (2026-04-15)

```sql
CASE 
    -- 規則 1: 特定工單號 → V1
    WHEN substring(mo_number, 1, 3) IN ('196','199','200','210','212','213')
    THEN 'V1'
    
    -- 規則 2-4: TASK_DEF_KEY_ 前綴匹配
    WHEN TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
    WHEN TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
    WHEN TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
    
    -- 規則 5: 預設
    ELSE COALESCE(substring(TASK_DEF_KEY_, 1, 2), 'Unknown')
END
```

---

## 影響分析

### ✅ 無功能影響

- **VTYPE 分類結果**: 完全一致，無任何差異
- **Gold 層數據**: 完全一致
- **業務指標**: 無影響
- **報表輸出**: 無影響

### ✅ 正面影響

| 優點 | 說明 |
|------|------|
| **邏輯更清晰** | 減少 2 條冗餘規則，邏輯更簡潔 |
| **維護更容易** | 只需維護一條工單號規則 |
| **效能更好** | 減少不必要的條件判斷 |
| **可讀性更好** | 規則更簡潔，更容易理解 |
| **一致性更高** | 避免規則衝突和優先順序混淆 |

---

## 修改的檔案

### SQL 腳本

- ✅ `sql/etl/dml/backfill_silver.sql` - 移除規則 1 和 2

### 文檔

- ✅ `memory-bank/systemPatterns.md` - 更新 VTYPE 分類邏輯說明
- ✅ `memory-bank/progress.md` - 記錄變更歷史
- ✅ `docs/03_metrics/03_ETL_Transformation_Pipeline.md` - 更新 Vx 版本歸屬邏輯
- ✅ `docs/DMP_Flowable_Technical_Documentation.md` - 更新 Vx Type 判定邏輯
- ✅ `docs/01_architecture/01_Architecture_Overview.md` - 更新 Vx 歸屬邏輯

### 驗證報告

- 📄 `scripts/validation/VTYPE_RULE_OVERLAP_REPORT.md` - 規則重疊驗證報告
- 📄 `scripts/validation/CNS_DG3_SMT_ST02_VERIFICATION_REPORT.md` - 特定線體驗證報告
- 📄 `scripts/validation/VERIFICATION_SUMMARY.md` - 驗證總結

---

## 後續步驟

### 建議執行（可選）

如需重新生成資料以應用新邏輯：

```bash
# 清空 Silver/Gold 層並重新生成
python scripts/etl/execute_etl.py --backfill --reset \
  --start 2025-01-01 --low-ram --step-days 10
```

**注意**: 由於邏輯變更不影響結果，重新執行 ETL 是可選的。

### 驗證步驟（可選）

```bash
# 驗證規則簡化後的結果
python scripts/validation/quick_rule_check.py

# 驗證特定線體
python scripts/validation/verify_rule3_only_impact.py
```

---

## 歷史背景

### 2026-02-26: 為什麼當初新增規則 1 和 2？

**問題**: NPE 與 DG3 廠區的 V1 資料短少（甚至為 0），全部湧入 V3

**原因**: Silver 層 `vx_type` 判斷序列將 `TASK_DEF_KEY_` 優先級置於頂層，導致本該由工單號 (MO) 強制轉為 V1 的特權工單被 `V3_` 開頭的自身屬性覆蓋

**解決方案**: 新增規則 1 和 2，將 DG3/NPE 廠區的特定工單優先轉為 V1

### 2026-04-15: 為什麼規則 1 和 2 現在變成冗餘？

**變更**: 新增規則 3「僅依工單號判斷」

**影響**: 規則 3 不檢查廠區條件，只要工單號符合就歸類為 V1，因此完全涵蓋了規則 1 和 2 的所有情況

**結論**: 規則 1 和 2 的廠區限制條件 (DG3/NPE) 變得多餘

---

## 審核與批准

| 角色 | 姓名 | 日期 | 簽名 |
|------|------|------|------|
| 驗證者 | Kiro AI Assistant | 2026-04-15 | ✅ |
| 審核者 | 使用者 | 2026-04-15 | 待確認 |

---

**變更完成日期**: 2026-04-15  
**文件版本**: 1.0
