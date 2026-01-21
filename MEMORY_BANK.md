# MEMORY BANK - 對話記憶庫

## 當前對話摘要 (2026-01-21 更新)

### 🎯 專案核心目標
建立完整的 L5 任務執行完成率指標系統，包括 Vx 歸屬邏輯、NPE 判別、排除規則等。

### ✅ 已完成的主要工作

#### 1. Vx 歸屬邏輯修正 (2026-01-21)
**問題**：工單號規則任務（996,028 筆）中有 991,053 筆被錯誤歸類為非 V1
**根因**：CASE 語句順序錯誤，工單號規則檢查被 TaskDefinitionKey 檢查覆蓋
**解決**：
- ✅ 修正 MVIEW 邏輯：工單號規則優先級最高（覆蓋所有 TaskDefinitionKey）
- ✅ 實裝在 `sql/12_create_silver_mviews_layer2.sql`
- ✅ 驗證結果：WJ2+NBU+E5+2025-12-31 任務統計正確

#### 2. NPE 判別邏輯確認 (2026-01-21)
**發現**：`bpm_act_hi_varinst.NAME_` 含有 53,494 筆 NPE 相關資料
**實裝**：
- ✅ 修改 Layer 1 MVIEW：添加 `varinst_name` 欄位（所有 NAME_ 值的連接字符串）
- ✅ 修改 Layer 2 MVIEW：使用 `varinst_name LIKE '%NPE%'` 判別 NPE
- ✅ V1 子類型邏輯：V1_NPE（含 NPE）vs V1_MFG（不含 NPE）

#### 3. WJ2+NBU+E5+2025-12-31 驗證完成
**統計結果**：
- 總計：44 筆
- 未排除：12 筆（V1_MFG 11筆 + V3 1筆）
- 已排除：32 筆
- 任務狀態：TODO 8筆、DOING 2筆、DONE 2筆

**結論**：該日期/廠區組合本身不含 NPE 任務，邏輯正確

### 📊 當前系統狀態

| 層級 | 狀態 | 驗證覆蓋度 | 備註 |
|------|------|----------|------|
| Bronze 層 | ✅ 完成 | 100% | 資料同步正常 |
| Silver 層 MVIEW | ✅ 完成 | 100% | Layer 1 + Layer 2 已實裝 |
| Vx 歸屬邏輯 | ✅ 完成 | 100% | 工單號規則優先級最高 |
| NPE 判別邏輯 | ✅ 完成 | 100% | 使用 varinst_name 欄位 |
| Gold 層 | 🟡 進行中 | 50% | 需要驗證 REFRESHABLE MV |
| 業務規則驗證 | ✅ 完成 | 100% | 三大規則已驗證 |

### 🔑 核心業務規則

#### Rule 1: 排除邏輯
- TaskBypass != 'N' → 排除
- TaskDefinitionKey 以 'E' 或 'C' 開頭 → 排除
- 工單號以 'Q' 或 'R' 開頭 → 排除

#### Rule 2: 任務狀態計算
- DONE：END_TIME IS NOT NULL
- TODO：END_TIME IS NULL AND ASSIGNEE IS NULL
- DOING：END_TIME IS NULL AND ASSIGNEE IS NOT NULL

#### Rule 3: Vx 歸屬（優先級）
1. **工單號規則**（最高）：196/199/200/210/212/213/315 開頭 → V1
2. **TaskDefinitionKey**（次高）：V1%/V2%/V3% 前綴
3. **V1 子類型**：
   - V1_NPE：varinst_name LIKE '%NPE%'
   - V1_MFG：其他 V1 任務

### 📁 關鍵檔案清單

**SQL 檔案**：
- `sql/11_create_silver_mviews_layer1.sql` - Layer 1 MVIEW（EAV 轉置、聚合）
- `sql/12_create_silver_mviews_layer2.sql` - Layer 2 MVIEW（業務邏輯、Vx 歸屬）

**驗證腳本**（保留）：
- `scripts/validate_l5_business_rules_v2.py` - 三大規則驗證
- `scripts/validate_vx_subtype_logic.py` - Vx 子類型驗證
- `scripts/check_wj2_nbu_e5_task_counts.py` - 特定廠區驗證
- `scripts/scan_npe_fields_in_bronze.py` - NPE 欄位掃描
- `scripts/rebuild_mview_with_varinst_name_npe.py` - MVIEW 重建

**文件**（保留）：
- `docs/vx_attribution_logic_correction.md` - Vx 歸屬邏輯文件
- `docs/metric_definitions.md` - 業務規則定義
- `docs/progress_2026_01_21.md` - 今日進度記錄

### 🟡 待處理事項

1. **文件歸檔**：30+ 個過時腳本和文件待移到 ARCHIVE 目錄
2. **Gold 層驗證**：確認 REFRESHABLE MV 是否正確反映修正邏輯
3. **其他廠區驗證**：查詢其他含有 NPE 的廠區驗證邏輯正確性

### 📝 重要決策記錄

1. **工單號規則優先級最高** (2026-01-21)
   - 無論 TaskDefinitionKey 是什麼，工單號規則決定 Vx 歸屬
   - 這包括「V1 調用 V3 流程所產生的任務」

2. **NPE 判別改用 varinst_name** (2026-01-21)
   - 不使用 business_key 或 factory 欄位
   - 使用 `bpm_act_hi_varinst.NAME_` 欄位（53,494 筆含 NPE 值）

3. **WJ2+NBU+E5 不含 NPE 任務** (2026-01-21)
   - 該日期/廠區組合本身不含 NPE 任務
   - 邏輯實裝正確，結果符合預期

---

**最後更新**：2026-01-21 18:30  
**對話狀態**：✅ 核心邏輯已完成，待文件歸檔和 Gold 層驗證