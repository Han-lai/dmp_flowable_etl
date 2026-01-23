DECLARE @startDateTime DATETIME = '2025-12-25 00:00:00';
DECLARE @endDateTime   DATETIME = '2025-12-25 23:59:59';
  

SELECT
    hi.PROC_INST_ID_ as processInstanceId,
    pd.KEY_ as processDefinitionKey,
    pd.NAME_ as processDefinitionName,

    -- 流程变量
    var_plant.TEXT_ as plant,
    var_factory.TEXT_  as factory,
    var_productionArea.TEXT_ as productionArea,
    var_lineName.TEXT_ as line,
    var_modelName.TEXT_ as modelName,
    var_deliveryArea.TEXT_ as deliveryArea,
    var_scheduleNumber.TEXT_ as scheduleNumber,
    var_moNumber.TEXT_ as moNumber,
    var_sapPlant.TEXT_ as sapPlant,
    var_sapProductGroup.TEXT_ as sapProductGroup,
    var_pallet.TEXT_ as pallet,
    var_transferNo.TEXT_ as transferNo,
    var_qBlockEventId.TEXT_ as qBlockEventId,
    var_defectSn.TEXT_ as defectSn,
    CONCAT('_', var_time.TEXT_) as timeKey,

    hti.ID_ as taskId,
    hti.TASK_DEF_KEY_ as taskDefinitionKey,
    hti.NAME_ as taskName,
    CASE
        WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
        WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
        ELSE 'TODO'
    END as taskStatus,
    CASE
        WHEN (
            SELECT TOP 1 LONG_
            FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
            WHERE TASK_ID_ = hti.ID_ AND NAME_ = 'autoComplete'
        ) = 1 THEN 'Y'
        ELSE 'N'
    END as taskBypass,

    hti.ASSIGNEE_ as taskAssignee,
    he.ADAccount as taskAssigneeAccount,
    he.EmpName as taskAssigneeName,
    CONVERT(VARCHAR, hti.START_TIME_, 120) as taskCreateTime,
    CONVERT(VARCHAR, hti.CLAIM_TIME_, 120) as taskClaimTime,
    CONVERT(VARCHAR, hti.END_TIME_, 120) as taskEndTime,

    CASE
        WHEN hti.END_TIME_ IS NOT NULL THEN
            ROUND(CAST(DATEDIFF(SECOND, hti.START_TIME_, hti.END_TIME_) AS FLOAT) / 60, 2)
        ELSE
            ROUND(CAST(DATEDIFF(SECOND, hti.START_TIME_, GETDATE()) AS FLOAT) / 60, 2)
    END as taskDurationMinutes,

    CASE
        WHEN hti.END_TIME_ IS NOT NULL THEN
            ROUND(CAST(DATEDIFF(SECOND, hti.CLAIM_TIME_, hti.END_TIME_) AS FLOAT) / 60, 2)
        ELSE
            ROUND(CAST(DATEDIFF(SECOND, hti.CLAIM_TIME_, GETDATE()) AS FLOAT) / 60, 2)
    END as taskWorkMinutes,

    hi.DELETE_REASON_ as deleteReason

FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant on hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ and var_plant.NAME_ = 'plant'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory on hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ and var_factory.NAME_ = 'factory'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_productionArea on hi.PROC_INST_ID_ = var_productionArea.PROC_INST_ID_ and var_productionArea.NAME_ = 'productionArea'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName on hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ and var_lineName.NAME_ = 'lineName'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_modelName on hi.PROC_INST_ID_ = var_modelName.PROC_INST_ID_ and var_modelName.NAME_ = 'modelName'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_deliveryArea on hi.PROC_INST_ID_ = var_deliveryArea.PROC_INST_ID_ and var_deliveryArea.NAME_ = 'deliveryArea'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_scheduleNumber on hi.PROC_INST_ID_ = var_scheduleNumber.PROC_INST_ID_ and var_scheduleNumber.NAME_ = 'scheduleNumber'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber on hi.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ and var_moNumber.NAME_ = 'moNumber'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_sapPlant on hi.PROC_INST_ID_ = var_sapPlant.PROC_INST_ID_ and var_sapPlant.NAME_ = 'sapPlant'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_sapProductGroup on hi.PROC_INST_ID_ = var_sapProductGroup.PROC_INST_ID_ and var_sapProductGroup.NAME_ = 'sapProductGroup'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_pallet on hi.PROC_INST_ID_ = var_pallet.PROC_INST_ID_ and var_pallet.NAME_ = 'pallet'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_transferNo on hi.PROC_INST_ID_ = var_transferNo.PROC_INST_ID_ and var_transferNo.NAME_ = 'transferNo'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_qBlockEventId on hi.PROC_INST_ID_ = var_qBlockEventId.PROC_INST_ID_ and var_qBlockEventId.NAME_ = 'qBlockEventId'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_defectSn on hi.PROC_INST_ID_ = var_defectSn.PROC_INST_ID_ and var_defectSn.NAME_ = 'defectSn'
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_time on hi.PROC_INST_ID_ = var_time.PROC_INST_ID_ and var_time.NAME_ = 'time'
LEFT JOIN APP_SRV_BPM.dbo.ACT_RE_PROCDEF pd ON hi.PROC_DEF_ID_ = pd.ID_
LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
LEFT JOIN APP_SRV_COMMON.dbo.HR_Employee he on hti.ASSIGNEE_ = he.EmpCode
WHERE 1=1
AND (
       hti.START_TIME_ BETWEEN @startDateTime AND @endDateTime
    OR hti.CLAIM_TIME_ BETWEEN @startDateTime AND @endDateTime
    OR hti.END_TIME_   BETWEEN @startDateTime AND @endDateTime
)
AND var_plant.TEXT_ = 'WJ2'
AND var_factory.TEXT_ = 'NBU'
AND var_lineName.TEXT_ = 'E5'


-- 查詢到的結果

'''
|processInstanceId                   |processDefinitionKey|processDefinitionName                        |plant|factory|productionArea|line|modelName   |deliveryArea|scheduleNumber|moNumber   |sapPlant|sapProductGroup|pallet         |transferNo|qBlockEventId|defectSn|timeKey|taskId                              |taskDefinitionKey|taskName                                              |taskStatus|taskBypass|taskAssignee|taskAssigneeAccount|taskAssigneeName|taskCreateTime     |taskClaimTime      |taskEndTime|taskDurationMinutes|taskWorkMinutes|deleteReason|
|------------------------------------|--------------------|---------------------------------------------|-----|-------|--------------|----|------------|------------|--------------|-----------|--------|---------------|---------------|----------|-------------|--------|-------|------------------------------------|-----------------|------------------------------------------------------|----------|----------|------------|-------------------|----------------|-------------------|-------------------|-----------|-------------------|---------------|------------|
|1178d911-e0aa-11f0-8766-badd3bc212ac|V3_5_3_9            |3.5.3.9 Finished Product Inspection & Release|WJ2  |NBU    |WJ2_NBU_MAIN  |E5  |ADP-140FB BA|            |              |20251224112|        |               |P2U092512240093|          |             |        |_      |117c3488-e0aa-11f0-8766-badd3bc212ac|V3_5_3_9_1       |3.5.3.9.1 Execute Final Product Inspection and Release|DOING     |N         |56629210    |HUINJ.ZHAO         |趙暉              |2025-12-24 17:22:29|2025-12-25 11:51:38|           |43,163.67          |42,054.52      |            |
|a83fa1af-e124-11f0-8766-badd3bc212ac|V3_5_1_10           |3.5.1.10 Resource Allocation                 |WJ2  |NBU    |WJ2_NBU_MAIN  |E5  |ADP-45DG BB |            |000058851982  |3152506536 |        |               |               |          |             |        |_      |a84b6195-e124-11f0-8766-badd3bc212ac|V3_5_1_10_1      |3.5.1.10.1 Call Resources                             |TODO      |N         |            |                   |                |2025-12-25 08:00:00|                   |           |42,286.15          |               |            |
|a8c8a825-e124-11f0-8766-badd3bc212ac|V3_5_1_10           |3.5.1.10 Resource Allocation                 |WJ2  |NBU    |WJ2_NBU_MAIN  |E5  |ADP-65KE BA |            |000058852719  |3152506697 |        |               |               |          |             |        |_      |a8cf860b-e124-11f0-8766-badd3bc212ac|V3_5_1_10_1      |3.5.1.10.1 Call Resources                             |TODO      |N         |            |                   |                |2025-12-25 08:00:01|                   |           |42,286.13          |               |            |
|a9607bab-e124-11f0-8766-badd3bc212ac|V3_5_1_10           |3.5.1.10 Resource Allocation                 |WJ2  |NBU    |WJ2_NBU_MAIN  |E5  |ADP-65AE BA |            |000058852838  |3152506743 |        |               |               |          |             |        |_      |a96360f1-e124-11f0-8766-badd3bc212ac|V3_5_1_10_1      |3.5.1.10.1 Call Resources                             |TODO      |N         |            |                   |                |2025-12-25 08:00:02|                   |           |42,286.12          |               |            |
|dc9cab8e-e155-11f0-8766-badd3bc212ac|V3_5_1_0            |3.5.1.0 Process Check                        |WJ2  |NBU    |WJ2_NBU_MAIN  |E5  |ADP-65KE BA |            |000058851564  |3152506512 |        |               |               |          |             |        |_      |dc9fb8e2-e155-11f0-8766-badd3bc212ac|V3_5_1_0_1       |3.5.1.0.1 MFG Check Model Requirements                |TODO      |N         |            |                   |                |2025-12-25 13:52:13|                   |           |41,933.93          |               |            |
'''