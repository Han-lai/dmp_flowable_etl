# bronze.common_flowable_task_stats 欄位來源追溯報告

## 🔍 關鍵發現

**bronze.common_flowable_task_stats 不是來自 ClickHouse 內的原生 Flowable 表**

- **實際來源**: `APP_SRV_COMMON.dbo.FlowableTaskStats` (MSSQL)
- **同步方式**: 增量同步，每15分鐘一次
- **追蹤欄位**: `LastUpdatedTime`
- **記錄數量**: 1,300,963 筆 (遠超過原生表的 52,497 筆)

## 📊 資料比對結果

| 表名 | 記錄數 | 時間範圍 | TaskId 重疊 |
|------|--------|----------|-------------|
| bronze.common_flowable_task_stats | 1,300,963 | 2025-07-24 ~ 2026-01-09 | - |
| bronze.bpm_act_hi_taskinst | 52,497 | 2025-01-22 ~ 2026-01-20 | **0 筆重疊** |
| bronze.bpm_act_hi_procinst | 17,974 | - | **0 筆重疊** |

## 🎯 欄位來源追溯表

| 欄位 | 最可能原生來源 | 推導規則/備註 | 信心等級 | 驗證方法 |
|------|----------------|---------------|----------|----------|
| **TaskId** | APP_SRV_COMMON.dbo.FlowableTaskStats.TaskId | 直接對應 | 高 | 已確認為 MSSQL 來源 |
| **ProcessInstanceId** | APP_SRV_COMMON.dbo.FlowableTaskStats.ProcessInstanceId | 直接對應 | 高 | 已確認為 MSSQL 來源 |
| **TaskDefinitionKey** | APP_SRV_COMMON.dbo.FlowableTaskStats.TaskDefinitionKey | 直接對應 | 高 | 已確認為 MSSQL 來源 |
| **TaskStatus** | APP_SRV_COMMON.dbo.FlowableTaskStats.TaskStatus | 直接對應 (DONE/DOING/TODO) | 高 | 已確認狀態分佈 |
| **TaskCreateTime** | APP_SRV_COMMON.dbo.FlowableTaskStats.TaskCreateTime | 直接對應 | 高 | 已確認為 MSSQL 來源 |
| **TaskClaimTime** | APP_SRV_COMMON.dbo.FlowableTaskStats.TaskClaimTime | 直接對應 (可為 NULL) | 高 | 已確認為 MSSQL 來源 |
| **TaskEndTime** | APP_SRV_COMMON.dbo.FlowableTaskStats.TaskEndTime | 直接對應 | 高 | 已確認為 MSSQL 來源 |
| **TaskAssigneeName** | APP_SRV_COMMON.dbo.FlowableTaskStats.TaskAssigneeName | 直接對應 | 高 | 已確認為 MSSQL 來源 |
| **TaskAssigneeAccount** | APP_SRV_COMMON.dbo.FlowableTaskStats.TaskAssigneeAccount | 直接對應 | 高 | 已確認為 MSSQL 來源 |
| **Plant** | APP_SRV_COMMON.dbo.FlowableTaskStats.Plant | 直接對應 | 高 | 已確認為 MSSQL 來源 |
| **Factory** | APP_SRV_COMMON.dbo.FlowableTaskStats.Factory | 直接對應 | 高 | 已確認為 MSSQL 來源 |
| **Line** | APP_SRV_COMMON.dbo.FlowableTaskStats.Line | 直接對應 | 高 | 已確認為 MSSQL 來源 |
| **MoNumber** | APP_SRV_COMMON.dbo.FlowableTaskStats.MoNumber | 直接對應 | 高 | 已確認為 MSSQL 來源 |

## ⚠️ 重要結論

1. **bronze.common_flowable_task_stats 是二次加工表**
   - 來源是 APP_SRV_COMMON 資料庫的已彙總表
   - 不能直接追溯到 Flowable 原生表 (ACT_HI_*)

2. **真正的原生來源追溯需要在 MSSQL 端進行**
   - 需要分析 APP_SRV_COMMON.dbo.FlowableTaskStats 如何產生
   - 可能涉及複雜的 ETL 邏輯和多表 JOIN

3. **ClickHouse 內的原生表資料不完整**
   - bronze.bpm_act_hi_taskinst 只有 5.2 萬筆記錄
   - bronze.common_flowable_task_stats 有 130 萬筆記錄
   - 兩者完全沒有重疊的 TaskId

## 🔧 建議後續行動

1. **如果需要真正的原生來源追溯**:
   - 需要在 MSSQL 端分析 APP_SRV_COMMON.dbo.FlowableTaskStats 的產生邏輯
   - 查看該表的 ETL 腳本或 View 定義

2. **如果只需要欄位對應**:
   - 當前的 bronze.common_flowable_task_stats 已經是可用的資料來源
   - 所有欄位都直接對應 MSSQL 來源表

3. **資料一致性檢查**:
   - 建議檢查 APP_SRV_COMMON.dbo.FlowableTaskStats 與 APP_SRV_BPM 原生表的關係
   - 確認資料完整性和時效性

## 📋 驗證狀態

- ✅ 確認資料來源 (APP_SRV_COMMON)
- ✅ 確認同步機制 (增量同步)
- ✅ 確認欄位對應 (直接對應)
- ❌ 原生 Flowable 表追溯 (需要 MSSQL 端分析)
- ❌ 資料完整性驗證 (需要跨資料庫比對)