# MView 完整建立指南

## 概述

本指南說明如何使用純 SQL 重新建立整個 MView 架構，包括 Silver 層和 Gold 層的所有 Materialized Views。

## 檔案結構

```
sql/
├── 00_execute_all_mviews.sql      # 執行順序說明和驗證腳本
├── 11_create_silver_mviews_layer1.sql  # Silver 層第一層（基礎聚合）
├── 12_create_silver_mviews_layer2.sql  # Silver 層第二層（業務邏輯）
├── 13_create_gold_mviews.sql           # Gold 層（最終指標）
└── README_MVIEW_SETUP.md               # 本檔案
```

## 執行順序

**⚠️ 重要：必須按以下順序執行，因為存在依賴關係**

### 1. 執行 Silver 層第一層
```sql
-- 執行檔案：11_create_silver_mviews_layer1.sql
-- 建立內容：
--   - mv_varinst_pivoted（EAV 轉置，包含所有變數名稱）
--   - mv_emp_user_groups（用戶群組聚合）
--   - mv_emp_node_codes（員工節點聚合）
--   - mv_emp_org_info（員工組織資訊）
--   - mv_task_status_summary（任務狀態聚合）
```

### 2. 執行 Silver 層第二層
```sql
-- 執行檔案：12_create_silver_mviews_layer2.sql
-- 建立內容：
--   - mv_fact_task_vx_attribution（任務 Vx 歸屬，包含 NPE 邏輯）
--   - mv_dim_config_user（配置用戶維度）
--   - mv_l5_metrics_realtime（L5 指標即時聚合）
--   - vw_fact_task_vx_attribution_realtime（查詢視圖）
```

### 3. 執行 Gold 層
```sql
-- 執行檔案：13_create_gold_mviews.sql
-- 建立內容：
--   - DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV（每日完成率快照）
--   - vw_daily_l5_completion_summary（業務友好視圖）
--   - vw_vx_type_summary（Vx 類型彙總）
--   - vw_factory_summary（廠區彙總）
--   - vw_v1_npe_mfg_comparison（NPE vs MFG 對比）
```

## 關鍵修正內容

### 1. NPE 邏輯修正
- **問題**：原本 `mv_varinst_pivoted` 的 WHERE 條件排除了 NPE 變數
- **修正**：移除 WHERE 過濾，包含所有變數名稱
- **結果**：V1_NPE 和 V1_MFG 子類型正確區分

### 2. 315% 規則修正
- **問題**：原本使用特定工單號 IN ('3152600035', '3152600036', '3152600037')
- **修正**：改為 LIKE '315%' 涵蓋所有 315 開頭的工單號
- **結果**：正確識別所有 315% 工單

### 3. POPULATE 關鍵字
- **修正**：所有 MView 都添加 POPULATE 關鍵字
- **結果**：MView 建立時自動填充歷史資料

## 驗證步驟

執行完成後，使用 `00_execute_all_mviews.sql` 中的驗證腳本：

### 1. 檢查 MView 建立狀態
```sql
SELECT database, name, engine, total_rows
FROM system.tables
WHERE database IN ('silver', 'gold') AND engine LIKE '%View%'
ORDER BY database, name;
```

### 2. 驗證 NPE 資料
```sql
-- 應該看到 V1_NPE 和 V1_MFG 兩種子類型
SELECT vx_subtype, COUNT(*) as count
FROM silver.mv_fact_task_vx_attribution
WHERE vx_type = 'V1'
GROUP BY vx_subtype;
```

### 3. 驗證 315% 規則
```sql
-- 應該看到大量 315% 工單（約 489,515 筆）
SELECT COUNT(*) as total_315_orders
FROM silver.mv_fact_task_vx_attribution
WHERE mo_number LIKE '315%';
```

## 預期結果

| MView 名稱 | 預期行數 | 關鍵驗證點 |
|-----------|---------|-----------|
| mv_varinst_pivoted | ~17,949 | 包含 NPE 資料（~2,895 筆） |
| mv_fact_task_vx_attribution | ~1,300,963 | V1_NPE: ~283 筆, V1_MFG: ~1,008,774 筆 |
| mv_l5_metrics_realtime | ~9,996 | V1_NPE: ~95 筆, V1_MFG: ~694,004 筆 |
| DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV | ~299 | 包含所有 Vx 類型和子類型 |

## 故障排除

### 1. MView 無資料
- 檢查 Bronze 層資料是否完整
- 確認執行順序正確
- 檢查是否有 POPULATE 關鍵字

### 2. NPE 資料缺失
- 確認 `mv_varinst_pivoted` 沒有 WHERE 過濾
- 檢查 Bronze 層是否有 NPE 變數（應該有 ~53,494 筆）

### 3. 315% 規則異常
- 確認使用 LIKE '315%' 而非 IN 特定工單號
- 檢查 Bronze 層工單號資料

## 重新執行

如需重新執行：

1. **完全重建**：按順序執行 11 → 12 → 13
2. **部分重建**：
   - 只重建 Gold 層：執行 13
   - 只重建 Silver Layer 2：執行 12 → 13
   - 只重建 Silver Layer 1：執行 11 → 12 → 13

## 注意事項

1. **執行時間**：完整重建可能需要數分鐘，視資料量而定
2. **資源使用**：POPULATE 會消耗較多 CPU 和記憶體
3. **依賴關係**：必須按順序執行，不可跳過或顛倒順序
4. **資料一致性**：建議在低峰時段執行，避免影響查詢效能

## 聯絡資訊

如有問題，請參考：
- `docs/mview_workflow_verification_report_2026_01_22.md` - 詳細驗證報告
- `docs/rules_quick_reference_2026_01_22.md` - 業務規則快速參考
- `MEMORY_BANK.md` - 完整專案記錄