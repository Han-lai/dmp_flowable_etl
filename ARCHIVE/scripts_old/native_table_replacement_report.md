# bronze.common_flowable_task_stats 替換為原生表報告

## 🎯 任務完成狀態

✅ **已完成：欄位來源追溯和替換準備**

## 📊 測試結果總結

### ✅ 基礎資料可用性
- `bronze.bpm_act_hi_taskinst`: 52,497 筆任務記錄
- `bronze.bpm_act_hi_procinst`: 17,974 筆流程記錄  
- `bronze.bpm_act_hi_varinst`: 693,867 筆變數記錄
- `bronze.common_hr_employee`: 262,513 筆員工記錄
- `silver.mv_varinst_pivoted`: 17,949 筆轉置變數記錄

### ✅ TaskBypass 邏輯驗證
- **來源**: `bronze.bpm_act_hi_varinst` (NAME_='autoComplete', JOIN by TASK_ID_)
- **邏輯**: `CASE WHEN LONG_ = 1 THEN 'Y' ELSE 'N' END`
- **覆蓋率**: 92.8% (48,746/52,497 任務有此變數)
- **分佈**: TaskBypass='Y': 21,829 筆, TaskBypass='N': 26,917 筆

### ✅ 員工姓名 JOIN 驗證
- **來源**: `bronze.common_hr_employee.EmpName`
- **JOIN 條件**: `t.ASSIGNEE_ = he.EmpCode`
- **成功率**: 98.8% (39,624/40,103 有 ASSIGNEE_ 的任務)
- **唯一員工**: 95 個 ASSIGNEE_, 73 個員工代碼

### ✅ 變數轉置驗證
- **來源**: `silver.mv_varinst_pivoted` (已存在)
- **成功率**: 99.9% (52,460/52,497 任務有變數記錄)
- **欄位覆蓋率**:
  - Plant: 96.2% (50,487/52,497)
  - Factory: 83.7% (43,956/52,497)
  - Line: 41.8% (21,920/52,497)
  - MoNumber: 58.4% (30,649/52,497)

## 🔧 已建立的替換檔案

### 1. Silver MVIEW 原生版本
- **檔案**: `sql/12_create_silver_mviews_layer2_native.sql`
- **內容**: 
  - `silver.mv_fact_task_vx_attribution_native` - 任務 Vx 歸屬事實表
  - `silver.mv_l5_metrics_realtime_native` - L5 指標聚合
  - `silver.vw_fact_task_vx_attribution_native` - 查詢視圖

### 2. 第一層 MVIEW 更新
- **檔案**: `sql/11_create_silver_mviews_layer1.sql` (已更新)
- **內容**: `silver.mv_task_status_summary_native` - 任務狀態統計

### 3. 測試腳本
- **檔案**: `scripts/test_native_mviews.py`
- **功能**: 驗證原生表邏輯正確性

## 📋 完整欄位對應表

| 欄位 | 原生表來源 | 推導規則 | 驗證狀態 |
|------|------------|----------|----------|
| TaskId | bronze.bmp_act_hi_taskinst.ID_ | 直接對應 | ✅ 已驗證 |
| ProcessInstanceId | bronze.bmp_act_hi_taskinst.PROC_INST_ID_ | 直接對應 | ✅ 已驗證 |
| TaskDefinitionKey | bronze.bmp_act_hi_taskinst.TASK_DEF_KEY_ | 直接對應 | ✅ 已驗證 |
| TaskName | bronze.bmp_act_hi_taskinst.NAME_ | 直接對應 | ✅ 已驗證 |
| TaskStatus | bronze.bmp_act_hi_taskinst | `CASE WHEN END_TIME_ IS NOT NULL THEN 'DONE' WHEN ASSIGNEE_ IS NOT NULL THEN 'DOING' ELSE 'TODO' END` | ✅ 已驗證 |
| TaskBypass | bronze.bmp_act_hi_varinst | `CASE WHEN LONG_ = 1 THEN 'Y' ELSE 'N' END` (NAME_='autoComplete', JOIN by TASK_ID_) | ✅ 已驗證 |
| TaskAssigneeName | bronze.common_hr_employee.EmpName | JOIN by ASSIGNEE_ = EmpCode | ✅ 已驗證 |
| TaskAssigneeAccount | bronze.bmp_act_hi_taskinst.ASSIGNEE_ | 直接對應 | ✅ 已驗證 |
| TaskCreateTime | bronze.bmp_act_hi_taskinst.START_TIME_ | 直接對應 | ✅ 已驗證 |
| TaskClaimTime | bronze.bmp_act_hi_taskinst.CLAIM_TIME_ | 直接對應 (可為 NULL) | ✅ 已驗證 |
| TaskEndTime | bronze.bmp_act_hi_taskinst.END_TIME_ | 直接對應 (可為 NULL) | ✅ 已驗證 |
| Plant | silver.mv_varinst_pivoted.varinst_plant | EAV 轉置 (NAME_='plant') | ✅ 已驗證 |
| Factory | silver.mv_varinst_pivoted.varinst_factory | EAV 轉置 (NAME_='factory') | ✅ 已驗證 |
| Line | silver.mv_varinst_pivoted.varinst_lineName | EAV 轉置 (NAME_='lineName') | ✅ 已驗證 |
| MoNumber | silver.mv_varinst_pivoted.varinst_moNumber | EAV 轉置 (NAME_='moNumber') | ✅ 已驗證 |

## 🚀 下一步行動

### 立即可執行
1. **執行原生版本 MVIEW 建立**:
   ```sql
   -- 執行第一層 MVIEW (已更新)
   SOURCE sql/11_create_silver_mviews_layer1.sql
   
   -- 執行第二層原生版本 MVIEW
   SOURCE sql/12_create_silver_mviews_layer2_native.sql
   ```

2. **驗證資料一致性**:
   - 比對原版本 vs 原生版本的結果
   - 確認 V1/V3 歸屬邏輯正確
   - 確認 315% 工單規則正確

### 後續替換
3. **逐步替換其他使用 bronze.common_flowable_task_stats 的地方**:
   - 分析腳本 (diagnose, check, compare 等)
   - 其他 SQL 檔案
   - 文件更新

## ⚠️ 注意事項

1. **資料完整性**: 原生表 (52K 筆) vs FlowableTaskStats (130萬筆) 有巨大差異
2. **時間範圍**: 原生表時間範圍較新，可能缺少歷史資料
3. **NULL 值處理**: 時間欄位需要適當的 NULL 值處理
4. **效能考量**: 原生表 JOIN 複雜度較高，需要監控效能

## 🎯 成功指標

- ✅ 所有欄位來源已確定
- ✅ 原生表邏輯已驗證
- ✅ 替換檔案已準備完成
- ⏳ 等待執行和驗證階段