import clickhouse_connect

client = clickhouse_connect.get_client(
    host='10.136.218.207', 
    port=8121, 
    username='default', 
    password='default'
)

# 重建 V_HI_BIZ_EVENT_INFO
print("=== 重建 V_HI_BIZ_EVENT_INFO ===")
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
        countIf(ti.END_TIME_ IS NULL AND ti.CLAIM_TIME_ IS NULL) AS TASK_TODO_CNT,
        countIf(ti.CLAIM_TIME_ IS NOT NULL AND ti.END_TIME_ IS NULL) AS TASK_DOING_CNT,
        countIf(ti.END_TIME_ IS NOT NULL AND (ti.DELETE_REASON_ IS NULL OR ti.DELETE_REASON_ = '') AND lower(coalesce(ti.DELETE_REASON_, '')) NOT LIKE '%auto%') AS TASK_DONE_CNT,
        countIf(ti.END_TIME_ IS NOT NULL AND lower(coalesce(ti.DELETE_REASON_, '')) LIKE '%auto%') AS TASK_AUTOCOMPLETE_CNT,
        countIf(ti.DELETE_REASON_ IS NOT NULL AND ti.DELETE_REASON_ != '') AS TASK_CANCELLED_CNT,
        sum(if(ti.CLAIM_TIME_ IS NOT NULL AND ti.END_TIME_ IS NOT NULL, dateDiff('second', ti.CLAIM_TIME_, ti.END_TIME_), 0)) AS TOTAL_WORK_DURATION_SEC
    FROM bronze.bpm_act_hi_taskinst AS ti
    INNER JOIN bronze.bpm_act_hi_procinst AS pi ON ti.PROC_INST_ID_ = pi.PROC_INST_ID_
    WHERE pi.BUSINESS_KEY_ IS NOT NULL AND pi.BUSINESS_KEY_ != ''
    GROUP BY pi.BUSINESS_KEY_
) AS t ON p.BUSINESS_KEY = t.BUSINESS_KEY
""")
print("View 重建完成")

# 驗證
print("\n=== 驗證 FIRST_PROC_DEF_NAME ===")
result = client.query("""
SELECT 
    BIZ_EVENT_KEY, FIRST_PROC_DEF_NAME, IS_IN_PROGRESS, PROCESS_COUNT
FROM silver.V_HI_BIZ_EVENT_INFO 
WHERE FIRST_PROC_DEF_NAME IS NOT NULL
LIMIT 10
""")
for row in result.result_rows:
    print(f"  {row[0][:30]}: {row[1][:40] if row[1] else 'N/A'} (進行中: {row[2]}, 流程數: {row[3]})")

# 在途流程健康度快照 - 現在可以直接查
print("\n=== 在途流程健康度快照 (直接查) ===")
result = client.query("""
SELECT 
    FIRST_PROC_DEF_NAME,
    count(*) AS EVENT_CNT
FROM silver.V_HI_BIZ_EVENT_INFO 
WHERE FINAL_END_TIME IS NULL AND FIRST_PROC_DEF_NAME IS NOT NULL
GROUP BY FIRST_PROC_DEF_NAME
ORDER BY EVENT_CNT DESC
LIMIT 10
""")
for row in result.result_rows:
    print(f"  {row[0][:45]}: {row[1]}")
