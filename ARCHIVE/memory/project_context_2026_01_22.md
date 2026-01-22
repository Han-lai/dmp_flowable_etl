# DMP Flowable 專案進度記錄 - 2026-01-22

## 📋 專案狀態總覽

### ✅ 已完成任務

#### 1. 315% 工單規則一致性修正 (已完成)
- **問題**: 系統對 315% 工單分類規則不一致，時間篩選邏輯有問題
- **解決方案**: 
  - 更新對帳腳本使用 `LIKE '315%'` 而非硬編碼數字
  - 修正 V1/V3 歸屬邏輯優先級 (工單規則優先於任務定義鍵)
  - 更新時間篩選邏輯使用 OR 條件
  - 執行 `scripts/execute_mview_time_fix.py` 修正 MVIEW 時間邏輯
- **驗證結果**: ClickHouse 和 MSSQL 對帳一致 (WJ2+NBU+E5 2025-12-30: 7 筆 V1 任務)

#### 2. bronze.common_flowable_task_stats 欄位來源追溯 (已完成)
- **問題**: bronze.common_flowable_task_stats 是二次加工表，需要追溯到原生 Flowable 表
- **發現**: 
  - bronze.common_flowable_task_stats (130萬筆) 來自 APP_SRV_COMMON.dbo.FlowableTaskStats
  - bronze.bpm_act_hi_taskinst (5.2萬筆) 是真正的原生表，但資料不重疊
- **解決方案**: 建立原生表版本的 Silver MVIEW 來替換 bronze.common_flowable_task_stats

### 🔄 進行中任務

#### 3. 替換 bronze.common_flowable_task_stats 為原生表 (✅ 基本完成)
- **狀態**: 核心邏輯驗證完成，可開始逐步替換
- **已完成**:
  - ✅ 完整欄位來源追溯和驗證
  - ✅ 建立原生版本 Silver MVIEW 檔案
  - ✅ 測試原生表邏輯正確性
  - ✅ 執行原生版本 MVIEW 建立 (簡化版)
  - ✅ 驗證 315% 工單規則正確性 (100% 歸類為 V1)
  - ✅ 比較分析原生版本 vs FlowableTaskStats
- **待執行**:
  - 🔄 逐步替換其他使用點
  - 🔄 處理時間欄位 NULL 值問題
  - 🔄 考慮歷史資料完整性方案

## 🎯 關鍵技術發現

### 欄位來源對應表
| 欄位 | 原生表來源 | 推導規則 | 驗證狀態 |
|------|------------|----------|----------|
| TaskId | bronze.bpm_act_hi_taskinst.ID_ | 直接對應 | ✅ |
| TaskStatus | bronze.bpm_act_hi_taskinst | CASE WHEN END_TIME_ IS NOT NULL THEN 'DONE' WHEN ASSIGNEE_ IS NOT NULL THEN 'DOING' ELSE 'TODO' END | ✅ |
| TaskBypass | bronze.bpm_act_hi_varinst | CASE WHEN LONG_ = 1 THEN 'Y' ELSE 'N' END (NAME_='autoComplete', JOIN by TASK_ID_) | ✅ |
| TaskAssigneeName | bronze.common_hr_employee.EmpName | JOIN by ASSIGNEE_ = EmpCode | ✅ |
| Plant/Factory/Line/MoNumber | silver.mv_varinst_pivoted | EAV 轉置 (已存在) | ✅ |

### 測試結果
- **TaskBypass 邏輯**: 92.8% 覆蓋率 (48,746/52,497 任務有 autoComplete 變數)
- **員工姓名 JOIN**: 98.8% 成功率
- **變數轉置**: 99.9% 成功率
- **資料完整性**: 原生表資料充足，邏輯正確
- **315% 工單規則**: ✅ 100% 正確歸類為 V1 (6,995 個任務)
- **原生版本 MVIEW**: ✅ 成功建立 (52,497 筆記錄)

## 📁 重要檔案

### 已建立的替換檔案
- `sql/12_create_silver_mviews_layer2_native.sql` - 原生版本 Silver MVIEW 第二層
- `sql/11_create_silver_mviews_layer1.sql` - 已更新第一層 MVIEW
- `scripts/test_native_mviews.py` - 測試腳本
- `scripts/native_table_replacement_report.md` - 完整替換報告
- `scripts/compare_native_vs_flowable_stats.py` - 比較分析腳本
- `silver.mv_fact_task_vx_attribution_native_simple` - ✅ 已建立並驗證

### 核心業務邏輯檔案
- `docs/metric_definitions.md` - 指標定義和業務規則
- `scripts/execute_mview_time_fix.py` - MVIEW 時間邏輯修正
- `sql/fix_mview_time_logic.sql` - 時間邏輯修正 SQL

## ⚠️ 重要注意事項

1. **資料範圍差異**: 原生表 (5.2萬筆) vs FlowableTaskStats (130萬筆)
2. **時間範圍**: 原生表較新，可能缺少歷史資料
3. **315% 工單規則**: 使用 `LIKE '315%'` 模式，工單規則優先於任務定義鍵
4. **時間邏輯**: 使用 OR 條件 `(START_TIME_ BETWEEN ... OR CLAIM_TIME_ BETWEEN ... OR END_TIME_ BETWEEN ...)`

## 🚀 下一步行動

### 立即執行 (當前任務)
1. 執行 `sql/12_create_silver_mviews_layer2_native.sql` 建立原生版本 MVIEW
2. 驗證原生版本 vs 原版本資料一致性
3. 確認 V1/V3 歸屬邏輯和 315% 工單規則正確

### 後續任務
4. 逐步替換其他使用 bronze.common_flowable_task_stats 的地方
5. 更新相關文件和腳本
6. 效能監控和優化

## 📊 專案指標

- **對帳一致性**: ✅ 已達成 (MSSQL vs ClickHouse)
- **資料血緣透明度**: ✅ 已達成 (原生表追溯完成)
- **系統穩定性**: 🔄 進行中 (替換階段)
- **效能優化**: ⏳ 待評估

---
**更新時間**: 2026-01-22
**更新人**: Kiro AI Assistant
**狀態**: 替換準備完成，等待執行階段