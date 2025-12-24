"""
建立 Silver Layer RMV (Refreshable Materialized View)
對齊 sql/06_create_silver_rmv.sql
"""
import clickhouse_connect
import time

client = clickhouse_connect.get_client(
    host='REDACTED_IP', 
    port=8121, 
    username='default', 
    password='default',
    settings={
        'allow_experimental_refreshable_materialized_view': 1
    }
)

print("=== 建立 Silver RMV (對齊 View 定義) ===\n")

# 0. RMV_PROC_VARIABLES_PIVOTED
print("0. 建立 RMV_PROC_VARIABLES_PIVOTED...")
try:
    client.command("DROP TABLE IF EXISTS silver.RMV_PROC_VARIABLES_PIVOTED")
    client.command("""
CREATE MATERIALIZED VIEW silver.RMV_PROC_VARIABLES_PIVOTED
REFRESH EVERY 1 DAY
ENGINE = ReplacingMergeTree()
ORDER BY PROC_INST_ID
SETTINGS allow_nullable_key = 1
AS
SELECT
    PROC_INST_ID_ AS PROC_INST_ID,
    anyIf(TEXT_, NAME_ = 'plant') AS PLANT,
    anyIf(TEXT_, NAME_ = 'factory') AS FACTORY,
    anyIf(TEXT_, NAME_ = 'region') AS REGION,
    anyIf(TEXT_, NAME_ = 'sapPlant') AS SAP_PLANT,
    anyIf(TEXT_, NAME_ = 'sapProductGroup') AS SAP_PROD_GRP,
    anyIf(TEXT_, NAME_ = 'lineName') AS LINE_NAME,
    anyIf(TEXT_, NAME_ = 'modelName') AS MODEL_NAME,
    anyIf(TEXT_, NAME_ = 'moNumber') AS MO_NUMBER,
    anyIf(TEXT_, NAME_ = 'scheduleNumber') AS SCH_NUMBER,
    anyIf(TEXT_, NAME_ = 'initiator') AS INITIATOR,
    anyIf(TEXT_, NAME_ = '_PROCESS_NODE_INFO') AS PROC_NODE_INFO,
    min(CREATE_TIME_) AS FIRST_VAR_CREATED_AT,
    max(LAST_UPDATED_TIME_) AS LAST_VAR_UPDATED_AT
FROM bronze.bpm_act_hi_varinst
WHERE NAME_ IN ('plant', 'factory', 'region', 'sapPlant', 'sapProductGroup', 
                'lineName', 'modelName', 'moNumber', 'scheduleNumber', 
                'initiator', '_PROCESS_NODE_INFO')
  AND PROC_INST_ID_ IS NOT NULL
  AND TASK_ID_ IS NULL
GROUP BY PROC_INST_ID_
    """)
    print("   ✅ 成功")
except Exception as e:
    print(f"   ❌ 失敗: {e}")

# 0.1 RMV_TASK_VARIABLES_PIVOTED (新增)
print("0.1 建立 RMV_TASK_VARIABLES_PIVOTED...")
try:
    client.command("DROP TABLE IF EXISTS silver.RMV_TASK_VARIABLES_PIVOTED")
    client.command("""
CREATE MATERIALIZED VIEW silver.RMV_TASK_VARIABLES_PIVOTED
REFRESH EVERY 1 DAY
ENGINE = ReplacingMergeTree()
ORDER BY (TASK_ID, PROC_INST_ID)
SETTINGS allow_nullable_key = 1
AS
SELECT
    TASK_ID_ AS TASK_ID,
    PROC_INST_ID_ AS PROC_INST_ID,
    anyIf(TEXT_, NAME_ = 'candidateUser') AS TASK_CANDIDATE_USER,
    anyIf(TEXT_, NAME_ = 'autoComplete') AS TASK_AUTO_COMPLETE,
    min(CREATE_TIME_) AS FIRST_VAR_CREATED_AT,
    max(LAST_UPDATED_TIME_) AS LAST_VAR_UPDATED_AT
FROM bronze.bpm_act_hi_varinst
WHERE NAME_ IN ('candidateUser', 'autoComplete')
  AND TASK_ID_ IS NOT NULL
GROUP BY TASK_ID_, PROC_INST_ID_
    """)
    print("   ✅ 成功")
except Exception as e:
    print(f"   ❌ 失敗: {e}")

# 先刷新變數表
print("\n--- 刷新變數表 ---")
for rmv in ['RMV_PROC_VARIABLES_PIVOTED', 'RMV_TASK_VARIABLES_PIVOTED']:
    try:
        client.command(f"SYSTEM REFRESH VIEW silver.{rmv}")
        print(f"  {rmv}: 刷新觸發成功")
    except Exception as e:
        print(f"  {rmv}: {e}")
time.sleep(5)  # 等待刷新完成

# 1. RMV_HI_PROC_TASK_NODE
print("\n1. 建立 RMV_HI_PROC_TASK_NODE...")
try:
    client.command("DROP TABLE IF EXISTS silver.RMV_HI_PROC_TASK_NODE")
    client.command("""
CREATE MATERIALIZED VIEW silver.RMV_HI_PROC_TASK_NODE
REFRESH EVERY 1 DAY
ENGINE = ReplacingMergeTree()
ORDER BY TASK_ID
SETTINGS allow_nullable_key = 1
AS
SELECT
    t.ID_ AS TASK_ID,
    t.PROC_INST_ID_ AS PROC_INST_ID,
    t.PROC_DEF_ID_ AS PROC_DEF_ID,
    t.TASK_DEF_KEY_ AS TASK_DEF_KEY,
    t.NAME_ AS TASK_NAME,
    t.ASSIGNEE_ AS ASSIGNEE,
    t.START_TIME_ AS START_TIME,
    t.CLAIM_TIME_ AS CLAIM_TIME,
    t.END_TIME_ AS END_TIME,
    t.DURATION_ AS DURATION_MS,
    t.DELETE_REASON_ AS DELETE_REASON,
    p.BUSINESS_KEY_ AS BUSINESS_KEY,
    
    if(t.CLAIM_TIME_ IS NOT NULL, dateDiff('second', t.START_TIME_, t.CLAIM_TIME_), NULL) AS IDLE_DURATION_SEC,
    if(t.CLAIM_TIME_ IS NOT NULL AND t.END_TIME_ IS NOT NULL, dateDiff('second', t.CLAIM_TIME_, t.END_TIME_), NULL) AS WORK_DURATION_SEC,
    if(t.END_TIME_ IS NOT NULL, dateDiff('second', t.START_TIME_, t.END_TIME_), NULL) AS TOTAL_DURATION_SEC,
    
    multiIf(
        t.DELETE_REASON_ IS NOT NULL AND t.DELETE_REASON_ != '', 'CANCELLED',
        t.ASSIGNEE_ IS NULL AND t.END_TIME_ IS NULL, 'TODO',
        t.ASSIGNEE_ IS NOT NULL AND t.END_TIME_ IS NULL, 'DOING',
        t.ASSIGNEE_ IS NOT NULL AND t.CLAIM_TIME_ IS NULL AND t.END_TIME_ IS NOT NULL, 'DONE_AUTO',
        t.END_TIME_ IS NOT NULL, 'DONE',
        'TODO'
    ) AS TASK_STATUS,
    
    if(tv.TASK_AUTO_COMPLETE = '1', 'Y', 'N') AS TASK_BYPASS,
    tv.TASK_CANDIDATE_USER,
    tv.TASK_AUTO_COMPLETE,
    il.CANDIDATE_USERS_LINK,
    
    v.PLANT,
    v.FACTORY,
    v.REGION,
    v.SAP_PLANT,
    v.SAP_PROD_GRP,
    v.LINE_NAME,
    v.MODEL_NAME,
    v.MO_NUMBER,
    v.SCH_NUMBER,
    
    pd.NAME_ AS PROC_DEF_NAME,
    pd.KEY_ AS PROC_DEF_KEY,
    e.DeptCodeLname AS DEPT_NAME

FROM bronze.bpm_act_hi_taskinst AS t
LEFT JOIN bronze.bpm_act_hi_procinst AS p ON t.PROC_INST_ID_ = p.PROC_INST_ID_
LEFT JOIN silver.RMV_PROC_VARIABLES_PIVOTED AS v ON t.PROC_INST_ID_ = v.PROC_INST_ID
LEFT JOIN silver.RMV_TASK_VARIABLES_PIVOTED AS tv ON t.ID_ = tv.TASK_ID
LEFT JOIN (
    SELECT 
        TASK_ID_,
        groupArray(USER_ID_) AS CANDIDATE_USERS_LINK
    FROM bronze.bpm_act_hi_identitylink
    WHERE TYPE_ = 'candidate' AND USER_ID_ IS NOT NULL
    GROUP BY TASK_ID_
) AS il ON t.ID_ = il.TASK_ID_
LEFT JOIN bronze.bpm_act_re_procdef AS pd ON t.PROC_DEF_ID_ = pd.ID_
LEFT JOIN bronze.common_hr_employee AS e ON t.ASSIGNEE_ = e.EmpCode
    """)
    print("   ✅ 成功")
except Exception as e:
    print(f"   ❌ 失敗: {e}")
