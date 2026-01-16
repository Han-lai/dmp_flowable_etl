import clickhouse_connect

client = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

# 1. 更新 V_HI_PROC_TASK_NODE
print("=== 更新 V_HI_PROC_TASK_NODE ===")
client.command("DROP VIEW IF EXISTS silver.V_HI_PROC_TASK_NODE")
client.command("""
CREATE VIEW silver.V_HI_PROC_TASK_NODE AS
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
    v.PLANT,
    v.FACTORY,
    v.REGION,
    v.SAP_PLANT,
    v.LINE_NAME,
    v.MODEL_NAME,
    pd.NAME_ AS PROC_DEF_NAME,
    e.DeptCodeLname AS DEPT_NAME
FROM bronze.bpm_act_hi_taskinst AS t
LEFT JOIN bronze.bpm_act_hi_procinst AS p ON t.PROC_INST_ID_ = p.PROC_INST_ID_
LEFT JOIN silver.V_PROC_VARIABLES_PIVOTED AS v ON t.PROC_INST_ID_ = v.PROC_INST_ID
LEFT JOIN bronze.bpm_act_re_procdef AS pd ON t.PROC_DEF_ID_ = pd.ID_
LEFT JOIN bronze.common_hr_employee AS e ON t.ASSIGNEE_ = e.EmpCode
""")
print("V_HI_PROC_TASK_NODE 更新完成")

# 2. 更新 V_HI_BIZ_EVENT_INFO
print("\n=== 更新 V_HI_BIZ_EVENT_INFO ===")
client.command("DROP VIEW IF EXISTS silver.V_HI_BIZ_EVENT_INFO")
client.command("""
CREATE VIEW silver.V_HI_BIZ_EVENT_INFO AS
SELECT
    p.BUSINESS_KEY AS BIZ_EVENT_KEY,
    p.FIRST_START_TIME,
    p.FINAL_END_TIME,
    p.TOTAL_DURATION_SEC,
    p.TOTAL_PROC_DURATION_SEC,
    p.PROCESS_COUNT,
    p.IS_IN_PROGRESS,
    p.FIRST_PROC_DEF_NAME,
    coalesce(t.TASK_TODO_CNT, 0) AS TASK_TODO_CNT,
    coalesce(t.TASK_DOING_CNT, 0) AS TASK_DOING_CNT,
    coalesce(t.TASK_DONE_CNT, 0) AS TASK_DONE_CNT,
    coalesce(t.TASK_AUTOCOMPLETE_CNT, 0) AS TASK_AUTOCOMPLETE_CNT,
    coalesce(t.TASK_CANCELLED_CNT, 0) AS TASK_CANCELLED_CNT,
    coalesce(t.TOTAL_WORK_DURATION_SEC, 0) AS TOTAL_WORK_DURATION_SEC
FROM (
    SELECT
        pi.BUSINESS_KEY_ AS BUSINESS_KEY,
        min(pi.START_TIME_) AS FIRST_START_TIME,
        if(countIf(pi.END_TIME_ IS NULL) = 0, max(pi.END_TIME_), NULL) AS FINAL_END_TIME,
        if(countIf(pi.END_TIME_ IS NULL) = 0, dateDiff('second', min(pi.START_TIME_), max(pi.END_TIME_)), NULL) AS TOTAL_DURATION_SEC,
        sum(if(pi.DURATION_ IS NOT NULL, toInt64(pi.DURATION_) / 1000, 0)) AS TOTAL_PROC_DURATION_SEC,
        count(*) AS PROCESS_COUNT,
        if(countIf(pi.END_TIME_ IS NULL) > 0, 1, 0) AS IS_IN_PROGRESS,
        anyIf(pd.NAME_, pi.SUPER_PROCESS_INSTANCE_ID_ IS NULL OR pi.SUPER_PROCESS_INSTANCE_ID_ = '') AS FIRST_PROC_DEF_NAME
    FROM bronze.bpm_act_hi_procinst AS pi
    LEFT JOIN bronze.bpm_act_re_procdef AS pd ON pi.PROC_DEF_ID_ = pd.ID_
    WHERE pi.BUSINESS_KEY_ IS NOT NULL AND pi.BUSINESS_KEY_ != ''
    GROUP BY pi.BUSINESS_KEY_
) AS p
LEFT JOIN (
    SELECT
        pi.BUSINESS_KEY_ AS BUSINESS_KEY,
        countIf(ti.ASSIGNEE_ IS NULL AND ti.END_TIME_ IS NULL) AS TASK_TODO_CNT,
        countIf(ti.ASSIGNEE_ IS NOT NULL AND ti.END_TIME_ IS NULL) AS TASK_DOING_CNT,
        countIf(ti.END_TIME_ IS NOT NULL AND ti.CLAIM_TIME_ IS NOT NULL AND (ti.DELETE_REASON_ IS NULL OR ti.DELETE_REASON_ = '')) AS TASK_DONE_CNT,
        countIf(ti.ASSIGNEE_ IS NOT NULL AND ti.CLAIM_TIME_ IS NULL AND ti.END_TIME_ IS NOT NULL AND (ti.DELETE_REASON_ IS NULL OR ti.DELETE_REASON_ = '')) AS TASK_AUTOCOMPLETE_CNT,
        countIf(ti.DELETE_REASON_ IS NOT NULL AND ti.DELETE_REASON_ != '') AS TASK_CANCELLED_CNT,
        sum(if(ti.CLAIM_TIME_ IS NOT NULL AND ti.END_TIME_ IS NOT NULL, dateDiff('second', ti.CLAIM_TIME_, ti.END_TIME_), 0)) AS TOTAL_WORK_DURATION_SEC
    FROM bronze.bpm_act_hi_taskinst AS ti
    INNER JOIN bronze.bpm_act_hi_procinst AS pi ON ti.PROC_INST_ID_ = pi.PROC_INST_ID_
    WHERE pi.BUSINESS_KEY_ IS NOT NULL AND pi.BUSINESS_KEY_ != ''
    GROUP BY pi.BUSINESS_KEY_
) AS t ON p.BUSINESS_KEY = t.BUSINESS_KEY
""")
print("V_HI_BIZ_EVENT_INFO 更新完成")

# 3. 驗證結果
print("\n=== 驗證 TASK_STATUS 分布 ===")
result = client.query("""
SELECT TASK_STATUS, count(*) AS cnt
FROM silver.V_HI_PROC_TASK_NODE
GROUP BY TASK_STATUS
ORDER BY cnt DESC
""")
print("TASK_STATUS | count")
print("-" * 30)
for row in result.result_rows:
    print(f"{row[0]:15} | {row[1]}")

print("\n=== 驗證 V_HI_BIZ_EVENT_INFO 任務統計 ===")
result2 = client.query("""
SELECT 
    sum(TASK_TODO_CNT) AS TODO,
    sum(TASK_DOING_CNT) AS DOING,
    sum(TASK_DONE_CNT) AS DONE,
    sum(TASK_AUTOCOMPLETE_CNT) AS DONE_AUTO,
    sum(TASK_CANCELLED_CNT) AS CANCELLED
FROM silver.V_HI_BIZ_EVENT_INFO
""")
print(f"TODO: {result2.result_rows[0][0]}")
print(f"DOING: {result2.result_rows[0][1]}")
print(f"DONE: {result2.result_rows[0][2]}")
print(f"DONE_AUTO: {result2.result_rows[0][3]}")
print(f"CANCELLED: {result2.result_rows[0][4]}")
