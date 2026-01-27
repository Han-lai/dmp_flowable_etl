#!/usr/bin/env python3
"""
驗證 MSSQL Reference SQL 的 12 筆結果
"""
import pymssql

conn = pymssql.connect(
    server='twtpesqldv2.delta.corp',
    port='1433',
    user='DMP_APP_SRV',
    password='APP@DB#01',
    database='APP_SRV_BPM'
)
cursor = conn.cursor()

print("=" * 100)
print("MSSQL Reference SQL 驗證")
print("條件: taskCreateTime BETWEEN '2025-12-31 00:00:00' AND '2025-12-31 23:59:59'")
print("      AND taskBypass='N' AND plant='WJ2' AND line='E5'")
print("=" * 100)

# Reference SQL
cursor.execute("""
SELECT * FROM (
SELECT
    hi.PROC_INST_ID_ AS processInstanceId,
    pd.KEY_ AS processDefinitionKey,
    pd.NAME_ AS processDefinitionName,
    -- 流程變數
    var_plant.TEXT_ AS plant,
    var_factory.TEXT_ AS factory,
    var_productionArea.TEXT_ AS productionArea,
    var_lineName.TEXT_ AS line,
    var_modelName.TEXT_ AS modelName,
    var_deliveryArea.TEXT_ AS deliveryArea,
    var_scheduleNumber.TEXT_ AS scheduleNumber,
    var_moNumber.TEXT_ AS moNumber,
    var_sapPlant.TEXT_ AS sapPlant,
    var_sapProductGroup.TEXT_ AS sapProductGroup,
    var_pallet.TEXT_ AS pallet,
    var_transferNo.TEXT_ AS transferNo,
    var_qBlockEventId.TEXT_ AS qBlockEventId,
    var_defectSn.TEXT_ AS defectSn,
    CONCAT('_' , var_time.TEXT_) AS timeKey,
    -- 任務資訊
    hti.ID_ AS taskId,
    hti.TASK_DEF_KEY_ AS taskDefinitionKey,
    hti.NAME_ AS taskName,
    CASE
        WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
        WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
        ELSE 'TODO'
    END AS taskStatus,
    -- Bypass 判斷
    CASE WHEN var_bypass.LONG_ = 1 THEN 'Y' ELSE 'N' END AS taskBypass,
    hti.ASSIGNEE_ AS taskAssignee,
    he.ADAccount AS taskAssigneeAccount,
    he.EmpName AS taskAssigneeName,
    CONVERT(VARCHAR, hti.START_TIME_, 120) AS taskCreateTime,
    CONVERT(VARCHAR, hti.CLAIM_TIME_, 120) AS taskClaimTime,
    CONVERT(VARCHAR, hti.END_TIME_, 120) AS taskEndTime,
    -- 總歷時
    CASE
        WHEN hti.END_TIME_ IS NOT NULL THEN
            ROUND(CAST(DATEDIFF(SECOND, hti.START_TIME_, hti.END_TIME_) AS FLOAT) / 60, 2)
        ELSE
            ROUND(CAST(DATEDIFF(SECOND, hti.START_TIME_, GETDATE()) AS FLOAT) / 60, 2)
    END AS taskDurationMinutes,
    -- 實際處理耗時
    CASE
        WHEN hti.CLAIM_TIME_ IS NULL THEN 0
        WHEN hti.END_TIME_ IS NOT NULL THEN
            ROUND(CAST(DATEDIFF(SECOND, hti.CLAIM_TIME_, hti.END_TIME_) AS FLOAT) / 60, 2)
        ELSE
            ROUND(CAST(DATEDIFF(SECOND, hti.CLAIM_TIME_, GETDATE()) AS FLOAT) / 60, 2)
    END AS taskWorkMinutes,
    hi.DELETE_REASON_ AS deleteReason
FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
INNER JOIN APP_SRV_BPM.dbo.ACT_RE_PROCDEF pd ON hi.PROC_DEF_ID_ = pd.ID_
INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
-- 流程層級變數
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_productionArea ON hi.PROC_INST_ID_ = var_productionArea.PROC_INST_ID_ AND var_productionArea.NAME_ = 'productionArea'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_modelName ON hi.PROC_INST_ID_ = var_modelName.PROC_INST_ID_ AND var_modelName.NAME_ = 'modelName'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_deliveryArea ON hi.PROC_INST_ID_ = var_deliveryArea.PROC_INST_ID_ AND var_deliveryArea.NAME_ = 'deliveryArea'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_scheduleNumber ON hi.PROC_INST_ID_ = var_scheduleNumber.PROC_INST_ID_ AND var_scheduleNumber.NAME_ = 'scheduleNumber'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber ON hi.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ AND var_moNumber.NAME_ = 'moNumber'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_sapPlant ON hi.PROC_INST_ID_ = var_sapPlant.PROC_INST_ID_ AND var_sapPlant.NAME_ = 'sapPlant'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_sapProductGroup ON hi.PROC_INST_ID_ = var_sapProductGroup.PROC_INST_ID_ AND var_sapProductGroup.NAME_ = 'sapProductGroup'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_pallet ON hi.PROC_INST_ID_ = var_pallet.PROC_INST_ID_ AND var_pallet.NAME_ = 'pallet'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_transferNo ON hi.PROC_INST_ID_ = var_transferNo.PROC_INST_ID_ AND var_transferNo.NAME_ = 'transferNo'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_qBlockEventId ON hi.PROC_INST_ID_ = var_qBlockEventId.PROC_INST_ID_ AND var_qBlockEventId.NAME_ = 'qBlockEventId'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_defectSn ON hi.PROC_INST_ID_ = var_defectSn.PROC_INST_ID_ AND var_defectSn.NAME_ = 'defectSn'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_time ON hi.PROC_INST_ID_ = var_time.PROC_INST_ID_ AND var_time.NAME_ = 'time'
-- Task 層級變數 (autoComplete)
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
-- 員工表
LEFT JOIN APP_SRV_COMMON.dbo.HR_Employee he ON hti.ASSIGNEE_ = he.EmpCode
) AS t
WHERE t.taskCreateTime BETWEEN '2025-12-31 00:00:00' AND '2025-12-31 23:59:59'
  AND taskBypass='N' 
  AND plant='WJ2' 
  AND line='E5'
""")

rows = cursor.fetchall()
columns = [desc[0] for desc in cursor.description]

print(f"\n總筆數: {len(rows)}")
print("\n" + "=" * 100)
print("12 筆資料明細")
print("=" * 100)

# 顯示關鍵欄位
key_cols = ['taskId', 'taskStatus', 'taskBypass', 'plant', 'line', 'factory', 'taskCreateTime', 'taskDefinitionKey']
col_indices = {col: columns.index(col) for col in key_cols if col in columns}

print(f"\n{'taskId':<40} {'status':<8} {'bypass':<6} {'plant':<6} {'line':<6} {'factory':<8} {'taskCreateTime':<20}")
print("-" * 110)
for row in rows:
    task_id = row[col_indices['taskId']][:38] if row[col_indices['taskId']] else 'NULL'
    status = row[col_indices['taskStatus']] or 'NULL'
    bypass = row[col_indices['taskBypass']] or 'NULL'
    plant = row[col_indices['plant']] or 'NULL'
    line = row[col_indices['line']] or 'NULL'
    factory = row[col_indices['factory']] or 'NULL'
    create_time = str(row[col_indices['taskCreateTime']])[:19] if row[col_indices['taskCreateTime']] else 'NULL'
    print(f"{task_id:<40} {status:<8} {bypass:<6} {plant:<6} {line:<6} {factory:<8} {create_time:<20}")

# 統計
print("\n" + "=" * 100)
print("狀態統計")
print("=" * 100)
status_counts = {}
for row in rows:
    status = row[col_indices['taskStatus']]
    status_counts[status] = status_counts.get(status, 0) + 1

for status, count in sorted(status_counts.items()):
    print(f"  {status}: {count}")

# 輸出 taskId 清單供對帳
print("\n" + "=" * 100)
print("TaskId 清單 (供對帳)")
print("=" * 100)
task_ids = [row[col_indices['taskId']] for row in rows]
for tid in sorted(task_ids):
    print(f"  '{tid}'")

conn.close()
